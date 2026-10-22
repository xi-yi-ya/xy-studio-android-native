"""Owned API graphs derived from the user's six active workflows.

No editor-mode bypass ambiguity: disabled LoRAs are absent from API graphs.
"""
import math
import secrets
from dataclasses import dataclass, field, asdict

STYLES = {
    'darkbrush': 'monochrome ink wash style',
    'dotmatrix': 'monochrome stippling style',
    'kidsdrawing': 'naive expressive sketch style',
    'neondrip': 'textured abstract style',
    'rainywindow': 'rainy window style',
    'retroanime': 'purple retro anime style',
    'softwatercolor': 'art deco watercolor style',
    'sunsetblur': 'ethereal motion blur style',
    'vintagetarot': 'vintage tarot style',
}
MODES = {'qwen': 'Qwen 图片生成', 'qwen_edit': 'Qwen 图片编辑',
         'krea': 'Krea2 图片生成', 'quad': 'Krea2 角色四视图',
         'h3_i2v': 'H3 图生视频', 'h3_ref': 'H3 参考生视频',
         'h3_t2v': 'H3 文生视频', 'h3_fl2v': 'H3 首尾帧视频', 'upscale': 'RFMSR 高清放大'}
RATIOS = ['1:1', '2:3', '3:2', '3:4', '4:3', '9:16', '16:9', '21:9']

def new_seed():
    """Choose once for a new request; queued/recovered jobs retain that value."""
    return secrets.randbelow(2**63)

def default_steps(mode):
    if mode not in MODES:
        raise ValueError('未知工作流')
    return 40 if mode.startswith('qwen') else 10 if mode=='quad' else 15 if mode=='upscale' else 8

def resolution(ratio, mp, multiple=32):
    if ratio not in RATIOS or not .1 <= mp <= 16:
        raise ValueError('比例或分辨率超出范围')
    a, b = map(int, ratio.split(':'))
    k = math.sqrt(mp * 1024 * 1024 / (a*b))
    return max(multiple, round(a*k/multiple)*multiple), max(multiple, round(b*k/multiple)*multiple)

def frames(seconds):
    if not .2 <= seconds <= 149:
        raise ValueError('时长超出范围')
    n = max(5, round(seconds * 24))
    return n + (5 - n % 17) % 17

@dataclass
class Generation:
    mode: str = 'qwen'
    prompt: str = ''
    ratio: str = '16:9'
    megapixels: float = 1.0
    seconds: float = 5.0
    seed: int = 42
    steps: int = 0
    cinema: bool = False
    cinema_strength: float = .4
    quad_lora: bool = True
    styles: list[str] = field(default_factory=list)
    scale: float = 2.0
    references: list[str] = field(default_factory=list)
    # Defaults retain original BF16 workflow. Explicit low-memory option available.
    qwen_int8: bool = False
    edit_follow_source: bool = True

    def validate(self):
        if type(self.edit_follow_source) is not bool: raise ValueError('编辑输出尺寸选项无效')
        if self.mode not in MODES: raise ValueError('未知工作流')
        resolution(self.ratio, self.megapixels)
        frames(self.seconds)
        if not 0 <= self.seed < 2**63: raise ValueError('种子必须为 0 至 2^63-1')
        if type(self.steps) is not int or not 0 <= self.steps <= 100: raise ValueError('采样步数必须为 0–100 的整数')
        if not 1 <= self.scale <= 8: raise ValueError('放大倍数范围 1–8')
        if not 0 <= self.cinema_strength <= 2: raise ValueError('LoRA 强度范围 0–2')
        if any(s not in STYLES for s in self.styles): raise ValueError('未知 Krea 风格')
        minimum = {'qwen_edit':1, 'quad':1,'h3_i2v':1,'h3_fl2v':2,'h3_ref':1,'upscale':1}.get(self.mode,0)
        maximum = {'qwen_edit':16,'h3_ref':9,'h3_fl2v':2}.get(self.mode,1 if minimum else 0)
        if not minimum <= len(self.references) <= maximum:
            raise ValueError(f'该工作流需要 {minimum}–{maximum} 张参考图；顺序即引用顺序')
        if self.mode != 'upscale' and not self.prompt.strip(): raise ValueError('请输入提示词')
        return self

def build(g: Generation, uploaded: list[str], prefix='AIStoryStudio'):
    g.validate()
    if len(uploaded) != len(g.references): raise ValueError('上传引用数不匹配')
    graph = {}
    def node(name, kind, **inputs):
        graph[name] = {'class_type':kind, 'inputs':inputs}
        return [name,0]
    width,height=resolution(g.ratio,g.megapixels,32 if g.mode.startswith('h3') or g.mode=='qwen_edit' else 8)
    refs=[node(f'ref{i}','LoadImage',image=p) for i,p in enumerate(uploaded)]
    if g.mode=='upscale':
        model=node('rf','RH_RFMSR_ModelLoader',checkpoint='rfmsr.safetensors',precision='bfloat16',memory_mode='unload_after_run')
        out=node('up','RH_RFMSR_Upscale',rfmsr_model=model,image=refs[0],scale=g.scale,steps=g.steps or default_steps(g.mode),flow_sigma=1.0,seed=g.seed,color_correction='wavelet',tile_mode='auto',tile_size=512,tile_stride=256)
    elif g.mode.startswith('h3'):
        model=node('model','UNETLoader',unet_name='10Eros_Max_h3_TURBO-hybrid_beta4_int8_convrot.safetensors',weight_dtype='default')
        if g.cinema:
            model=node('cinema','LoraLoaderModelOnly',model=model,lora_name='minimax h3\\Minimax H3真实电影质感V0.1.safetensors',strength_model=g.cinema_strength)
        clip=node('clip','CLIPLoader',clip_name='qwen3vl_32b_minimax_h3_int8_convrot.safetensors',type='minimax',device='default')
        vae=node('vae','VAELoader',vae_name='minimax_h3_video_vae_fp16.safetensors')
        audio=node('audio_vae','VAELoader',vae_name='minimax_h3_audio_vae_fp32.safetensors')
        inputs=dict(clip=clip,vae=vae,prompt=g.prompt,width=width,height=height,length=frames(g.seconds))
        if g.mode=='h3_ref':
            inputs.update(audio_vae=audio,ref_image_size='match')
            inputs.update({f'ref_images.ref_image_{i}':r for i,r in enumerate(refs)})
            cond=node('cond','MiniMaxH3ReferenceToVideo',**inputs)
        else:
            if refs: inputs['first_frame']=refs[0]
            if len(refs)>1: inputs['last_frame']=refs[1]
            cond=node('cond','MiniMaxH3ImageToVideo',**inputs)
        guide=node('guide','BasicGuider',model=model,conditioning=cond)
        noise=node('noise','RandomNoise',noise_seed=g.seed)
        sampler=node('sampler','KSamplerSelect',sampler_name='res_multistep')
        sigmas=node('sigmas','BasicScheduler',model=model,scheduler='simple',steps=g.steps or default_steps(g.mode),denoise=1.0)
        samples=node('sample','SamplerCustomAdvanced',noise=noise,guider=guide,sampler=sampler,sigmas=sigmas,latent_image=['cond',1])
        out=node('decode','VAEDecode',samples=samples,vae=vae)
        sound=node('sound','VAEDecodeAudio',samples=samples,vae=audio)
        video=node('video','CreateVideo',images=out,audio=sound,fps=24.0,bit_depth=8,color_space='sRGB',codec='none')
        node('output','SaveVideo',video=video,filename_prefix=prefix,format='auto',**{'format.codec':'auto'})
        return graph
    else:
        qwen=g.mode.startswith('qwen')
        unet=('qwen_image_2.1_int8_convrot.safetensors' if g.qwen_int8 else 'qwen_image_2.1_bf16.safetensors') if qwen else ('krea2_turbo_fp8_scaled.safetensors' if g.mode=='quad' else 'krea2_turbo_fp8.safetensors')
        clipname=('qwen3vl_8b_int8_convrot.safetensors' if g.qwen_int8 else 'qwen3vl_8b_bf16.safetensors') if qwen else 'qwen3vl_4b_fp8_scaled.safetensors'
        model=node('model','UNETLoader',unet_name=unet,weight_dtype='default')
        if g.mode == 'qwen_edit':
            model=node('qwen_cache','QwenImage21Cache',model=model,device='auto',dtype='default')
        clip=node('clip','CLIPLoader',clip_name=clipname,type='qwen_image' if qwen else 'krea2',device='default')
        vae=node('vae','VAELoader',vae_name='qwen_image_2.1_vae_bf16.safetensors' if qwen else 'qwen_image_vae.safetensors')
        latent=node('latent','EmptyLatentImage',width=width,height=height,batch_size=1)
        if qwen:
            extra={}
            if refs:
                extra['vae']=vae
                extra.update({f'images.image_{i+1}':r for i,r in enumerate(refs)})
            positive=node('encode','TextEncodeQwenImage21',clip=clip,prompt=g.prompt,negative_prompt='',resolution=0 if refs else 1024,**extra)
            negative=['encode',1]
            if refs and g.edit_follow_source:
                latent=['encode',2]
                del graph['latent']
        elif g.mode=='quad':
            if g.quad_lora: model=node('quad_lora','LoraLoaderModelOnly',model=model,lora_name='Krea2\\QuadView_krea2_v1.safetensors',strength_model=1.0)
            source=node('source','VAEEncode',pixels=refs[0],vae=vae)
            model=node('patch','Krea2EditModelPatch',model=model,source_latent=source,source_image=refs[0],vae=vae,target_latent=latent,ref_boost=1.0,ref_boost_a=1.0,fit_mode='fit')
            positive=node('encode','Krea2EditGroundedEncode',clip=clip,prompt=g.prompt,image=refs[0],grounding_px=0)
            negative=node('negative','Krea2EditGroundedEncode',clip=clip,prompt='',image=refs[0],grounding_px=768)
        else:
            for i,style in enumerate(g.styles): model=node(f'style{i}','LoraLoaderModelOnly',model=model,lora_name=f'Krea2\\krea2_{style}.safetensors',strength_model=1.0)
            prompt=g.prompt + ''.join(', '+STYLES[s] for s in g.styles)
            positive=node('encode','CLIPTextEncode',clip=clip,text=prompt)
            negative=node('negative','ConditioningZeroOut',conditioning=positive)
        samples=node('sample','KSampler',model=model,positive=positive,negative=negative,latent_image=latent,seed=g.seed,steps=g.steps or default_steps(g.mode),cfg=1.0,sampler_name='euler',scheduler='simple',denoise=1.0)
        out=node('decode','VAEDecode',samples=samples,vae=vae)
    if g.mode.startswith('qwen'):
        node('output','SaveImageAdvanced',images=out,filename_prefix=prefix,format='png',**{'format.bit_depth':'16-bit' if g.mode=='qwen' else '8-bit','format.input_color_space':'sRGB'})
    else: node('output','SaveImage',images=out,filename_prefix=prefix)
    return graph

def preflight(graph, info):
    """Check closure, installed nodes and exact loader filenames before enqueue."""
    for name,n in graph.items():
        kind=n['class_type']
        if kind not in info: raise ValueError(f'ComfyUI 缺少节点：{kind}')
        schema=info[kind].get('input',{}).get('required',{})
        for key,value in n['inputs'].items():
            if isinstance(value,list) and len(value)==2:
                if value[0] not in graph: raise ValueError(f'断开的工作流连接：{name}.{key}')
            elif key in ('unet_name','clip_name','vae_name','lora_name','checkpoint'):
                options=schema.get(key,[None])[0]
                if isinstance(options,list) and value not in options:
                    raise ValueError(f'ComfyUI 未找到模型：{value}')
    return True
