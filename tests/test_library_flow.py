"""The user chooses adoption; generation/replay never choose a new library result."""
import json
from dataclasses import asdict
import pytest
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from studio import service as module
from studio.service import StudioService
from studio.storage import LIBRARY_TARGET, atomic_json, Project
from studio.workflows import Generation
from studio.asset_library import AssetLibrary

app=QApplication.instance() or QApplication([])
@pytest.fixture
def service(tmp_path,monkeypatch):
 monkeypatch.setattr(module,'QSettings',lambda *args:QSettings(str(tmp_path/'settings.ini'),QSettings.IniFormat))
 monkeypatch.setattr(module.keyring,'get_password',lambda *args:None)
 s=StudioService();s.load(tmp_path/'project',create=True);s.project.data['queue_paused']=True
 yield s
 s.shutdown()

def image(s,tmp_path,name='舞台',color='blue'):
 p=tmp_path/(name+'.png');Image.new('RGB',(96,64),color).save(p)
 return s.dispatch('library.import',{'kind':'image','paths':[str(p)]})[0]

def test_unassigned_generation_reopen_adopt_and_detach_preserve_identity(service,tmp_path):
 s=service;file=image(s,tmp_path)
 actor=s.dispatch('asset.from_media',{'kind':'characters','file':file})
 assert s.project.get(actor)['name']=='舞台'
 old=dict(s.project.get(actor))
 job_id=s.dispatch('generation.submit',{'generation':asdict(Generation(prompt='舞台新灯光'))})
 job=s.project.data['jobs'][-1];out='outputs/result.png';Image.new('RGB',(96,64),'green').save(s.project.file(out))
 job.update(status='completed',outputs=[out]);s.project.attach_output(job,out);atomic_json(s.project.file('jobs/'+job_id+'.json'),job)
 assert job['target']==LIBRARY_TARGET and s.project.get(actor)==old
 row=AssetLibrary(s.project).get(out);identity=row['id']
 assert not row['owners'] and not row['deletedOwner'] and row['name']=='图片 1'
 root=s.project.root;s.load(tmp_path/'other',create=True);s.load(root)
 assert s.project.get(actor)==old
 s.dispatch('asset.use_media',{'id':actor,'file':out})
 assert s.project.get(actor)['image']==out and len(s.project.get(actor)['versions'])==2
 s.dispatch('asset.use_media',{'id':actor,'file':out})
 assert len(s.project.get(actor)['versions'])==2
 assert AssetLibrary(s.project).get(out)['id']==identity
 s.dispatch('asset.delete',{'id':actor})
 assert s.project.file(file).exists() and s.project.file(out).exists()
 assert s.project.data['schema']==1

def test_again_restores_original_ordered_references_after_result_adopted(service,tmp_path):
 s=service;a=image(s,tmp_path,'人物');b=image(s,tmp_path,'舞台')
 g=asdict(Generation(mode='qwen_edit',prompt='把图1人物放入图2',references=[a,b],steps=40,qwen_int8=True))
 s.dispatch('generation.submit',{'generation':g});j=s.project.data['jobs'][-1]
 out='outputs/composite.png';Image.new('RGB',(96,64),'red').save(s.project.file(out));j.update(status='completed',outputs=[out])
 actor=s.dispatch('asset.from_media',{'kind':'characters','file':out,'name':'初音未来'})
 restored=s.dispatch('generation.defaults',{'mode':'qwen_edit'})
 assert restored['references']==[a,b] and restored['prompt']==g['prompt']
 assert restored['steps']==40 and restored['seed']!=str(g['seed'])
 preview=s.dispatch('library.preview',{'file':out})
 assert preview['generation']['references']==[a,b] and preview['generation']['seed']=='42'
 assert s.project.get(actor)['image']==out
 rows=s.dispatch('references.describe',{'files':[a,b]})
 assert [r['name'] for r in rows]==['人物','舞台'] and all(r['media'] for r in rows)

def test_agent_video_opens_review_without_creating_shot_or_image(service,tmp_path):
 s=service;file=image(s,tmp_path)
 args={'mode':'h3_i2v','prompt':'integrated_multimodal_description: Slow camera.\noverall_soundscape: N/A\nnon_diegetic_music: N/A','references':[file]}
 s._accept_message({'role':'assistant','content':'请确认视频参数','tool_calls':[{'id':'video','type':'function','function':{'name':'generate','arguments':json.dumps(args)}}]})
 assert s.pending and s.pending['generation']['mode']=='h3_i2v'
 assert s.pending['generation']['references']==[file] and s.pending['targetName']=='视频库'
 s.dispatch('review.respond',{'id':s.pending['id'],'accepted':True})
 assert len(s.project.data['jobs'])==1 and s.project.data['jobs'][0]['target']==LIBRARY_TARGET
 assert not s.project.data['shots'] and not s.project.data['characters'] and not s.project.data['scenes']

def test_adopt_name_and_legacy_description_are_independent_from_library(service,tmp_path):
 s=service;file=image(s,tmp_path,'原图片名')
 actor=s.dispatch('asset.from_media',{'kind':'characters','file':file,'name':'角色名'})
 s.project.get(actor)['description']='旧项目资料需要保留'
 s.dispatch('asset.rename',{'id':actor,'name':'新名称'})
 assert s.project.get(actor)['description']=='旧项目资料需要保留'
 assert AssetLibrary(s.project).get(file)['name']=='原图片名'
 s.dispatch('asset.rename',{'id':actor,'name':''})
 assert s.project.get(actor)['name']=='原图片名'
 with pytest.raises(ValueError):s.dispatch('asset.use_media',{'id':actor,'file':'../escape.png'})

def test_legacy_pending_resume_preserves_ids_but_requires_adoption(service,tmp_path,monkeypatch):
 s=service;file=image(s,tmp_path)
 actor=s.dispatch('asset.from_media',{'kind':'characters','file':file})
 job={'id':'old-job','target':actor,'prompt_id':'known-comfy-id','generation':asdict(Generation(prompt='旧任务')),'status':'detached'}
 s.project.data['jobs'].append(job);s.project.save()
 monkeypatch.setattr(s,'_spawn',lambda *args:None)
 s.start_job(job)
 assert job['library_only'] and job['id']=='old-job' and job['target']==actor
 out='outputs/resumed.png';Image.new('RGB',(96,64),'green').save(s.project.file(out));job.update(status='completed',outputs=[out])
 s.project.attach_output(job,out)
 assert s.project.get(actor)['image']==file
 assert not AssetLibrary(s.project).get(out)['owners']
 assert Project(s.project.root).data['jobs'][-1]['library_only']

def test_library_delete_restore_persists_without_losing_history_or_original(service,tmp_path):
 s=service;file=image(s,tmp_path,'生成结果')
 job={'id':'completed','target':LIBRARY_TARGET,'status':'completed','generation':asdict(Generation(prompt='角色三视图')),'outputs':[file]}
 s.project.data['jobs'].append(job);s.project.save()
 identity=AssetLibrary(s.project).get(file)['id'];original=s.project.file(file).read_bytes()
 s.dispatch('context.add_media',{'file':file})
 s.dispatch('library.delete',{'file':file})
 assert not s.media_context and AssetLibrary(s.project).query('image')['total']==0
 assert AssetLibrary(s.project).query('image',trash=True)['items'][0]['id']==identity
 assert s.project.file(file).read_bytes()==original and job['outputs']==[file]
 assert s.dispatch('references.describe',{'files':[file]})[0]['trashed']
 root=s.project.root;s.load(tmp_path/'other',create=True);s.load(root)
 assert AssetLibrary(s.project).query('image')['total']==0
 with pytest.raises(ValueError,match='回收站'):s.dispatch('context.add_media',{'file':file})
 with pytest.raises(ValueError,match='回收站'):s.dispatch('generation.submit',{'generation':asdict(Generation(mode='qwen_edit',prompt='edit',references=[file]))})
 s.dispatch('library.restore',{'file':file})
 assert AssetLibrary(s.project).get(file)['id']==identity
 assert AssetLibrary(s.project).query('image',trash=True)['total']==0
 assert s.project.data['jobs'][0]['outputs']==[file]

def test_delete_protects_selected_assets_pending_inputs_and_paths(service,tmp_path):
 s=service;file=image(s,tmp_path)
 actor=s.dispatch('asset.from_media',{'kind':'characters','file':file})
 with pytest.raises(ValueError,match='正在被使用'):s.dispatch('library.delete',{'file':file})
 s.dispatch('asset.delete',{'id':actor})
 job=s.dispatch('generation.submit',{'generation':asdict(Generation(mode='qwen_edit',prompt='edit',references=[file]))})
 with pytest.raises(ValueError,match='未完成'):s.dispatch('library.delete',{'file':file})
 s.dispatch('task.cancel',{'id':job})
 with pytest.raises(ValueError):s.dispatch('library.delete',{'file':'../outside.png'})
 s.dispatch('library.delete',{'file':file})
 assert s.project.file(file).is_file()

def test_deleted_legacy_output_is_not_readopted_during_replay(service,tmp_path):
 s=service;file=image(s,tmp_path)
 actor=s.project.add('characters','旧角色')
 job={'id':'legacy','target':actor['id'],'status':'completed','generation':asdict(Generation()),'outputs':[file]}
 s.project.data['jobs'].append(job);s.project.save()
 s.dispatch('library.delete',{'file':file})
 s.project.attach_output(job,file)
 assert not actor['image'] and not actor['versions']
 assert not AssetLibrary(s.project).query('image')['total']
 actor['versions'].append({'id':'old-version','file':file,'kind':'image'})
 with pytest.raises(ValueError,match='回收站'):s.dispatch('version.use',{'id':actor['id'],'version':'old-version'})
