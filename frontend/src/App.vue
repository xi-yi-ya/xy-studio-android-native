<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue';
import {
  PanelLeft,
  LayoutGrid,
  UsersRound,
  Mountain,
  Clapperboard,
  ListTodo,
  Settings2,
  Smartphone,
  ChevronDown,
  Sparkles,
  Plus,
  Search,
  Cloud as CloudCheck,
  ArrowUpRight,
  FolderOpen,
  MoreHorizontal,
  Film,
  History,
  Check,
  ImagePlus,
  Download,
  Pencil,
  X,
  Pause,
  Play,
  RotateCcw,
  CircleCheck,
  Clock3,
  ZoomIn,
  ZoomOut,
  Link2,
  ExternalLink,
} from 'lucide-vue-next';
import { useStudio } from './stores/studio';
import type { Asset, GenerationInput, Page, Shot, Suggestion, Task, Version } from './types';
import AssetCard from './components/AssetCard.vue';
import ShotCard from './components/ShotCard.vue';
import MediaThumb from './components/MediaThumb.vue';
import StudioDialog from './components/StudioDialog.vue';
import AssistantPanel from './components/AssistantPanel.vue';
import TimelinePanel from './components/TimelinePanel.vue';
import VideoPreview from './components/VideoPreview.vue';
import GenerationForm from './components/GenerationForm.vue';
import SettingsPanel from './components/SettingsPanel.vue';
import TaskProgress from './components/TaskProgress.vue';
import GenerationDetails from './components/GenerationDetails.vue';
import MessageText from './components/MessageText.vue';
import MediaLibrary from './components/MediaLibrary.vue';
import ReferenceImages from './components/ReferenceImages.vue';
import LanConnection from './components/LanConnection.vue';
import {isLan} from './lan';
import { command } from './gateway';
import './mobile.css';

const store = useStudio();
const openPhone = () => command('lan.open').catch(error => store.notify(String(error)));
const nav = [
  { page: 'projects', title: '项目', icon: LayoutGrid },
  { page: 'characters', title: '角色资产', icon: UsersRound },
  { page: 'scenes', title: '场景资产', icon: Mountain },
  { page: 'shots', title: '分镜工作区', icon: Clapperboard },
  { page: 'images', title: '图片库', icon: ImagePlus },
  { page: 'videos', title: '视频库', icon: Film },
  { page: 'tasks', title: '任务与历史', icon: ListTodo },
] as const;
const titles: Record<Page, string> = {
  projects: '你的创作空间',
  characters: '角色资产',
  scenes: '场景资产',
  shots: '分镜工作区',
  images: '图片资产库',
  videos: '视频资产库',
  tasks: '任务与历史',
  settings: '工作台设置',
};
const subtitles: Record<Page, string> = {
  projects: '每一个故事，都值得被认真记录。',
  characters: '让故事里的每个人，有自己的模样。',
  scenes: '为你的故事，搭建一个可以回到的世界。',
  shots: '把想象连成镜头，让故事慢慢发生。',
  images: '导入和生成的每个版本，都能在这里找到。',
  videos: '先生成或导入片段，再选用到你的分镜。',
  tasks: '每一次尝试，都留在它所属的故事里。',
  settings: '按照你的习惯，安排创作空间。',
};
const search = ref('');
const assets = computed(() =>
  store.project.assets.filter((a) => a.kind === store.page && a.name.includes(search.value)),
);
const shots = computed(() =>
  store.project.shots.filter((s) => `${s.name} ${s.description}`.includes(search.value)),
);
const taskFilter = ref('all');
const tasks = computed(() =>
  [...store.project.tasks]
    .reverse()
    .filter((t) => taskFilter.value === 'all' || t.status === taskFilter.value),
);
const activeTask = computed(
  () =>
    store.project.tasks.find((t) => t.id === store.state?.activeJob) ||
    store.project.tasks.find((t) =>
      ['new', 'submitting', 'queued', 'running', 'downloading', 'cancel_requested'].includes(
        t.status,
      ),
    ),
);
const modal = ref<
  | 'edit'
  | 'generate'
  | 'link'
  | 'history'
  | 'preview'
  | 'project'
  | 'review'
  | 'delete'
  | 'pick'
  | 'adopt'
  | null
>(null);
const targetId = ref('');
const pickKind = ref<'image' | 'video'>('image'),
  pickFile = ref(''),
  pickName = ref(''),
  pickPreview = ref<Version | null>(null);
const adoptFile = ref(''),
  adoptKind = ref<'image' | 'video'>('image'),
  adoptDestination = ref('characters'),
  adoptShot = ref('');
function openPick(id = '', kind: 'image' | 'video' = 'image') {
  targetId.value = id;
  pickKind.value = kind;
  pickFile.value = '';
  pickName.value = '';
  pickPreview.value = null;
  edit.value.kind = store.page === 'scenes' ? 'scenes' : 'characters';
  modal.value = 'pick';
}
async function pick(file: string) {
  pickFile.value = file;
  pickPreview.value = await store.previewMedia(file);
}
async function savePick() {
  if (!pickFile.value) return;
  const id = targetId.value
    ? (await store.useMedia(targetId.value, pickFile.value), targetId.value)
    : await store.addFromMedia(edit.value.kind, pickFile.value, pickName.value);
  modal.value = null;
  store.select(id);
  store.notify('素材已添加，图库原文件和生成记录仍保留');
}
function openAdopt(file: string, kind: 'image' | 'video') {
  adoptFile.value = file;
  adoptKind.value = kind;
  pickName.value = '';
  adoptDestination.value = kind === 'video' ? 'shot' : 'characters';
  adoptShot.value =
    store.project.shots.find((x) => x.id === store.selectedId)?.id ||
    store.project.shots[0]?.id ||
    '';
  modal.value = 'adopt';
}
async function saveAdopt() {
  if (adoptDestination.value === 'shot') {
    if (!adoptShot.value) {
      store.notify('请先添加分镜，再选择使用这份素材');
      return;
    }
    await store.useMedia(adoptShot.value, adoptFile.value);
    modal.value = null;
    navigate('shots');
    await locate(adoptShot.value);
  } else {
    const kind = adoptDestination.value as Asset['kind'];
    const id = await store.addFromMedia(kind, adoptFile.value, pickName.value);
    modal.value = null;
    navigate(kind);
    store.select(id);
  }
  store.notify('已选用素材，其他生成结果继续保存在库中');
}
async function libraryGenerate(kind: 'image' | 'video', previous?: GenerationInput) {
  await openGenerate('', kind, undefined, previous);
}
function preventDrag(event: Event) {
  event.preventDefault();
}

const historyJobId = ref<string | null>(null);
const historyTask = computed(() => store.project.tasks.find((t) => t.id === historyJobId.value));
const historyVersions = computed(() => historyTask.value?.results || target.value?.versions || []);
const target = computed(
  () =>
    store.project.assets.find((a) => a.id === targetId.value) ||
    store.project.shots.find((s) => s.id === targetId.value),
);
const edit = ref({
  name: '',
  description: '',
  duration: 5,
  kind: 'characters' as Asset['kind'],
});
const gen = ref<GenerationInput>({
  mode: 'qwen',
  prompt: '',
  ratio: '16:9',
  megapixels: 1,
  seconds: 5,
  seed: '42',
  steps: 0,
  cinema: false,
  cinema_strength: 0.4,
  quad_lora: true,
  qwen_int8: false,
  styles: [],
  scale: 2,
  references: [],
});
const suggestion = ref<Suggestion | null>(null);
const selectedLinks = ref<string[]>([]);
const preview = ref<Version | null>(null);
const zoom = ref(1);
const projectName = ref('');
const storyEditing = ref(false);
const contentArea = ref<HTMLElement>();
const compact = ref(false);
const statusNames: Record<string, string> = {
  ready: '待制作',
  queued: '等待中',
  running: '生成中',
  completed: '已完成',
  new: '待执行',
  submitting: '提交中',
  downloading: '保存结果',
  cancel_requested: '取消中',
  unknown: '状态未知',
  detached: '已断开',
  cancelled: '已取消',
  failed: '失败',
};

function navigate(page: Page) {
  store.page = page;
  search.value = '';
  if (contentArea.value) contentArea.value.scrollTop = 0;
}
function openEdit(id?: string) {
  targetId.value = id || '';
  const item = target.value;
  edit.value = {
    name: item?.name || '',
    description: item?.description || '',
    duration: item && 'duration' in item ? item.duration : 5,
    kind: store.page === 'scenes' ? 'scenes' : 'characters',
  };
  modal.value = 'edit';
}
async function saveEdit() {
  if (!target.value) return;
  if (target.value && 'duration' in target.value)
    await store.editAsset(targetId.value, edit.value.name.trim(), edit.value.description);
  else await store.rename(targetId.value, edit.value.name);
  modal.value = null;
  store.notify('资料已保存');
}
async function openGenerate(
  id: string,
  kind: 'image' | 'video' = 'image',
  s?: Suggestion,
  previous?: GenerationInput,
) {
  if (!store.hasProject) {
    store.notify('请先新建或打开项目');
    return;
  }
  targetId.value = '';
  suggestion.value = s || null;
  gen.value = JSON.parse(
    JSON.stringify(previous || s?.generation || (await store.defaults('', undefined, kind))),
  );
  modal.value = 'generate';
}
async function confirmGeneration() {
  if (suggestion.value) await store.reviewSuggestion(suggestion.value, true, gen.value);
  else await store.queueGeneration(targetId.value, gen.value);
  modal.value = null;
  suggestion.value = null;
  navigate(gen.value.mode.startsWith('h3') ? 'videos' : 'images');
  store.notify('任务已加入队列，完成后在素材库选择满意的结果');
}
async function cancelGeneration() {
  if (suggestion.value) await store.reviewSuggestion(suggestion.value, false);
  modal.value = null;
  suggestion.value = null;
}
function openLink(id: string) {
  targetId.value = id;
  const item = target.value;
  selectedLinks.value = item && 'assetIds' in item ? [...item.assetIds] : [];
  modal.value = 'link';
}
async function saveLinks() {
  await store.link(targetId.value, selectedLinks.value);
  modal.value = null;
  store.notify('素材关联已更新');
}
function openHistory(id: string) {
  targetId.value = id;
  historyJobId.value = null;
  modal.value = 'history';
}
function openTaskHistory(task: Task) {
  targetId.value = task.targetId;
  historyJobId.value = task.id;
  modal.value = 'history';
}
function openPreview(v: Version) {
  preview.value = v;
  zoom.value = 1;
  modal.value = 'preview';
}
function previewAsset(id: string) {
  const a = store.project.assets.find((a) => a.id === id);
  const v = a?.versions.find((v) => v.id === a.current);
  if (v) openPreview(v);
  else store.notify('这个素材还没有图片');
}
async function locate(id: string) {
  store.select(id);
  const s = store.project.shots.find((s) => s.id === id);
  if (s) store.fold(id, false);
  search.value = '';
  await nextTick();
  document.getElementById(`shot-${id}`)?.scrollIntoView({ block: 'start', behavior: 'smooth' });
}
async function locateMedia(id: string) {
  const shot = store.project.shots.find((s) => s.id === id),
    asset = store.project.assets.find((a) => a.id === id);
  if (!shot && !asset) {
    store.notify('原条目已删除，素材文件仍可使用');
    return;
  }
  navigate(shot ? 'shots' : asset!.kind);
  store.select(id);
  if (shot) store.fold(id, false);
  await nextTick();
  document
    .querySelector(`[data-testid="${shot ? 'shot' : 'asset'}-${id}"]`)
    ?.scrollIntoView({ block: 'center' });
}
watch(
  () => store.state,
  async () => {
    const v = preview.value;
    if (
      modal.value === 'preview' &&
      v?.kind === 'video' &&
      !v.url &&
      v.error === '正在准备兼容预览'
    ) {
      const fresh = await store.previewMedia(v.file);
      if (modal.value === 'preview' && preview.value?.id === v.id) preview.value = fresh;
    }
  },
);
async function addShot() {
  const id = await store.newShot();
  locate(id);
}
function allCollapsed(value: boolean) {
  store.project.shots.forEach((s) => store.fold(s.id, value));
}
async function review(s: Suggestion) {
  suggestion.value = s;
  if (s.name === 'generate')
    await openGenerate('', s.generation?.mode.startsWith('h3') ? 'video' : 'image', s);
  else modal.value = 'review';
}
async function persist() {
  await store.save();
  store.notify('项目已保存');
}
async function toggleStory() {
  if (storyEditing.value) await store.saveStory(store.project.story);
  storyEditing.value = !storyEditing.value;
}
function confirmDelete(id: string) {
  targetId.value = id;
  modal.value = 'delete';
}
async function deleteTarget() {
  await store.remove(targetId.value);
  modal.value = null;
}
const reviewDetails = computed(() => {
  const s = suggestion.value;
  if (!s) return [];
  if (s.name === 'set_story') return [{ label: '故事内容', text: String(s.args.text || '') }];
  const item =
    store.project.assets.find((a) => a.id === s.args.id) ||
    store.project.shots.find((a) => a.id === s.args.id);
  const details = [
    {
      label: s.name === 'add_item' ? '名称' : '修改对象',
      text: String(s.args.name || item?.name || '当前条目'),
    },
    { label: '内容描述', text: String(s.args.description || '') },
  ];
  if (s.name === 'add_item')
    details.unshift({
      label: '创建类型',
      text:
        ({ characters: '角色', scenes: '场景', shots: '分镜' } as Record<string, string>)[
          String(s.args.kind)
        ] || '素材',
    });
  if (Array.isArray(s.args.materials))
    details.push({
      label: '关联素材',
      text:
        s.args.materials
          .map((id) => store.project.assets.find((a) => a.id === id)?.name || '素材已移除')
          .join('、') || '无',
    });
  return details;
});
const pendingRecords = computed(() =>
  store.project.tasks.filter(
    (t) =>
      t.status !== 'completed' &&
      (historyTask.value
        ? t.id === historyTask.value.id
        : !!target.value && t.targetId === targetId.value),
  ),
);
watch(
  () => store.project.id,
  () => {
    modal.value = null;
    search.value = '';
  },
);
void store.initialize();
onMounted(() => {
  if (window.innerWidth < 1100) store.assistantOpen = false;
  for (const event of ['dragstart', 'dragover', 'drop'])
    document.addEventListener(event, preventDrag, true);
});
onBeforeUnmount(() => {
  for (const event of ['dragstart', 'dragover', 'drop'])
    document.removeEventListener(event, preventDrag, true);
});
</script>
<template>
  <div class="studio-shell" :class="{ compact, 'lan-shell': isLan }">
    <LanConnection v-if="isLan" />
    <header class="topbar">
      <button class="brand" @click="navigate('projects')" aria-label="XY Studio 项目">
        <img src="/media/xy-logo.jpg" alt="XY" /><strong>XY Studio</strong></button
      ><span class="top-divider" /><button class="project-switch" @click="navigate('projects')">
        {{ store.project.name }}<ChevronDown :size="14" /></button
      ><button class="save-status" :disabled="!store.hasProject" @click="persist">
        <CloudCheck :size="14" />{{ store.hasProject ? '保存项目' : '尚未打开'
        }}<span>本地项目</span>
      </button>
      <div class="top-spacer" />
      <button
        class="btn top-generate"
        aria-label="生成图片"
        :disabled="!store.hasProject"
        @click="openGenerate('', 'image')"
      >
        <ImagePlus :size="15" /><span>生成图片</span></button
      ><button
        class="btn top-generate"
        aria-label="生成视频"
        :disabled="!store.hasProject"
        @click="openGenerate('', 'video')"
      >
        <Film :size="15" /><span>生成视频</span></button
      ><span class="prototype-badge">创作工作台</span
      ><button
        class="btn assistant-toggle"
        aria-label="AI 助手"
        :class="{ active: store.assistantOpen }"
        @click="store.assistantOpen = !store.assistantOpen"
      >
        <Sparkles :size="16" /><span>AI 助手</span>
      </button>
    </header>
    <div class="shell-body">
      <nav class="sidebar" aria-label="主导航">
        <div class="sidebar-label">工作空间</div>
        <button
          v-for="item in nav"
          :key="item.page"
          class="nav-item"
          :class="{ active: store.page === item.page }"
          :aria-label="item.title"
          :title="item.title"
          :disabled="!store.hasProject && item.page !== 'projects'"
          :aria-current="store.page === item.page ? 'page' : undefined"
          @click="navigate(item.page)"
        >
          <component :is="item.icon" :size="18" :stroke-width="1.6" /><span>{{ item.title }}</span
          ><span v-if="item.page === 'tasks' && store.pendingTasks" class="nav-count">{{
            store.pendingTasks
          }}</span>
        </button>
        <div class="sidebar-project">
          <div><span class="project-dot" /><span>当前项目</span></div>
          <strong>{{ store.project.name }}</strong>
          <p>{{ store.project.shots.length }} 个镜头 · {{ store.totalDuration }} 秒</p>
        </div>
        <div class="sidebar-bottom">
          <button v-if="!isLan" class="nav-item" aria-label="手机连接" title="手机连接" @click="openPhone">
            <Smartphone :size="18" :stroke-width="1.6" /><span>手机连接</span>
          </button>
          <button
            class="nav-item"
            :class="{ active: store.page === 'settings' }"
            aria-label="设置"
            title="设置"
            @click="navigate('settings')"
          >
            <Settings2 :size="18" :stroke-width="1.6" /><span>设置</span>
          </button>
          <div class="workspace-signature">
            <span class="tiny-logo">XY</span
            ><span
              >让故事，发生。<small>Workbench / v{{ store.state?.version }}</small></span
            >
          </div>
        </div>
      </nav>
      <main class="main-workspace">
        <div ref="contentArea" class="workspace-scroll">
          <div class="workspace-content">
            <header class="page-heading">
              <div>
                <div class="breadcrumb">
                  {{ store.project.name }}<span>/</span>{{ titles[store.page] }}
                </div>
                <h1>{{ titles[store.page] }}</h1>
                <p>{{ subtitles[store.page] }}</p>
              </div>
              <div class="page-heading-actions">
                <template v-if="store.page === 'shots'"
                  ><button
                    class="btn"
                    @click="allCollapsed(!store.project.shots.every((s) => s.collapsed))"
                  >
                    <PanelLeft :size="14" />{{
                      store.project.shots.every((s) => s.collapsed) ? '展开全部' : '折叠全部'
                    }}</button
                  ><button class="btn btn-primary" @click="addShot">
                    <Plus :size="16" />添加镜头
                  </button></template
                ><button
                  v-else-if="store.page === 'characters' || store.page === 'scenes'"
                  class="btn btn-primary"
                  @click="openPick()"
                >
                  <Plus :size="16" />{{
                    store.page === 'characters' ? '添加角色' : '添加场景'
                  }}</button
                ><button
                  v-else-if="store.page === 'projects'"
                  class="btn btn-primary"
                  @click="
                    projectName = '';
                    modal = 'project';
                  "
                >
                  <Plus :size="16" />新建项目</button
                ><button v-else-if="store.page === 'tasks'" class="btn" @click="store.toggleQueue">
                  <Play v-if="store.paused" :size="15" /><Pause v-else :size="15" />{{
                    store.paused ? '继续待执行队列' : '暂停待执行队列'
                  }}
                </button>
              </div>
            </header>
            <div v-if="store.connectionError" class="error-banner">
              {{ store.connectionError
              }}<button class="text-action" @click="store.connectionError = ''">已了解</button>
            </div>
            <div v-if="store.state?.error" class="error-banner">
              {{ store.state.error
              }}<button class="text-action" @click="store.api('error.clear')">已了解</button>
            </div>
            <div v-if="store.persistenceError" class="error-banner">
              {{ store.persistenceError }}
            </div>
            <section v-if="activeTask" class="active-generation surface" aria-label="当前生成任务">
              <div>
                <strong>{{ activeTask.targetName }}</strong
                ><span class="muted"
                  >{{ activeTask.kind === 'video' ? '视频生成' : '图片生成' }} · 待完成
                  {{ store.pendingTasks }} 项</span
                >
              </div>
              <TaskProgress :task="activeTask" :paused="store.paused" />
              <button class="text-action" @click="store.page = 'tasks'">查看任务</button>
            </section>
            <template v-if="store.page === 'shots'">
              <section class="story-card surface">
                <div class="flex items-center justify-between mb-2">
                  <h2>故事描述</h2>
                  <button
                    class="icon-btn"
                    :aria-label="storyEditing ? '保存故事描述' : '编辑故事描述'"
                    @click="toggleStory"
                  >
                    <Check v-if="storyEditing" :size="15" /><Pencil v-else :size="15" />
                  </button>
                </div>
                <textarea
                  v-if="storyEditing"
                  v-model="store.project.story"
                  aria-label="故事描述"
                  rows="3"
                />
                <p v-else>
                  {{ store.project.story || '写下一段故事，从一句话开始也可以。' }}
                </p>
                <footer>
                  <span class="story-tag"><Film :size="12" />短故事</span
                  ><span>{{ store.project.shots.length }} 个镜头</span
                  ><span>{{ store.totalDuration }} 秒</span
                  ><span class="story-caption">素材 → 分镜图 → 视频</span>
                </footer>
              </section>
              <div class="section-toolbar">
                <div class="flex items-center gap-2">
                  <h2>镜头列表</h2>
                  <span class="number-badge">{{ store.project.shots.length }}</span>
                </div>
                <label class="search-field"
                  ><Search :size="14" /><input
                    v-model="search"
                    aria-label="搜索镜头"
                    placeholder="搜索镜头…"
                /></label>
              </div>
              <div class="shot-list">
                <ShotCard
                  v-for="shot in shots"
                  :key="shot.id"
                  :shot="shot"
                  :index="store.project.shots.findIndex((s) => s.id === shot.id)"
                  @delete="confirmDelete"
                  @edit="openEdit"
                  @choose="openPick"
                  @link="openLink"
                  @preview="openPreview"
                />
                <div v-if="!shots.length" class="empty-state surface">
                  <Clapperboard :size="35" :stroke-width="1.2" />
                  <h3>{{ search ? '没有找到这个镜头' : '你的第一个镜头' }}</h3>
                  <p>
                    {{
                      search
                        ? '试试镜头名称或描述中的其他词。'
                        : '把故事拆成一个画面，再让角色走进来。'
                    }}
                  </p>
                  <button class="btn btn-primary" @click="search ? (search = '') : addShot()">
                    {{ search ? '清除搜索' : '添加镜头' }}
                  </button>
                </div>
                <button v-if="shots.length" class="add-shot-row" @click="addShot">
                  <Plus :size="17" />添加下一个镜头
                </button>
              </div>
            </template>
            <template v-else-if="store.page === 'characters' || store.page === 'scenes'">
              <div class="section-toolbar asset-toolbar">
                <span class="muted"
                  >{{ assets.length }} 个{{ store.page === 'characters' ? '角色' : '场景'
                  }}<span class="toolbar-hint">右键查看更多操作 · 双击图片放大</span></span
                ><label class="search-field"
                  ><Search :size="14" /><input
                    v-model="search"
                    aria-label="搜索素材"
                    placeholder="搜索名称…"
                /></label>
              </div>
              <div class="asset-grid">
                <AssetCard
                  v-for="asset in assets"
                  :key="asset.id"
                  :asset="asset"
                  @delete="confirmDelete"
                  @edit="openEdit"
                  @choose="openPick"
                  @history="openHistory"
                  @preview="previewAsset"
                /><button v-if="!search" class="create-asset" @click="openPick()">
                  <span><Plus :size="25" :stroke-width="1.3" /></span
                  ><strong>{{
                    store.page === 'characters' ? '添加一个角色' : '添加一个场景'
                  }}</strong
                  ><small>从图片库选择满意的图片</small>
                </button>
              </div>
              <div v-if="!assets.length && search" class="empty-state">
                <Search :size="30" />
                <h3>没有找到这个素材</h3>
                <button class="btn" @click="search = ''">清除搜索</button>
              </div>
            </template>
            <template v-else-if="store.page === 'images' || store.page === 'videos'"
              ><MediaLibrary
                :kind="store.page === 'images' ? 'image' : 'video'"
                @preview="openPreview"
                @locate="locateMedia"
                @generate="libraryGenerate"
                @adopt="openAdopt"
            /></template>
            <template v-else-if="store.page === 'projects'">
              <div class="project-grid">
                <button
                  v-for="p in store.projects"
                  :key="p.id"
                  class="project-card surface"
                  @click="store.openProject(p.id)"
                >
                  <div class="project-cover"><FolderOpen :size="32" :stroke-width="1.3" /></div>
                  <div>
                    <span class="project-card-caption">最近打开的项目</span>
                    <h3>{{ p.name }}</h3>
                    <p>{{ p.story }}</p>
                    <footer>打开项目<ArrowUpRight :size="16" /></footer>
                  </div>
                </button>
              </div>
              <section class="welcome-note">
                <span class="welcome-icon"><Sparkles :size="23" /></span>
                <div>
                  <h3>从一个想法，到一个完整的故事。</h3>
                  <p>
                    打开已有
                    project.json，或在新文件夹创建项目。旧项目的素材、关联关系和历史会保留。
                  </p>
                  <div class="flex gap-3 mt-4">
                    <button class="btn btn-primary" @click="store.openProject()">
                      <FolderOpen :size="15" />打开项目</button
                    ><button v-if="store.hasProject" class="btn" @click="store.folder">
                      <ExternalLink :size="15" />打开项目文件夹
                    </button>
                  </div>
                </div>
              </section>
            </template>
            <template v-else-if="store.page === 'tasks'">
              <div class="task-stats">
                <div class="surface">
                  <Clock3 :size="19" /><span
                    >进行中<strong>{{ store.pendingTasks }}</strong></span
                  >
                </div>
                <div class="surface">
                  <CircleCheck :size="19" /><span
                    >已完成<strong>{{
                      store.project.tasks.filter((t) => t.status === 'completed').length
                    }}</strong></span
                  >
                </div>
                <div class="surface">
                  <History :size="19" /><span
                    >全部记录<strong>{{ store.project.tasks.length }}</strong></span
                  >
                </div>
              </div>
              <div class="task-table surface">
                <div class="task-table-head">
                  <h2>生成记录<span class="mock-tag ml-2">真实任务</span></h2>
                  <select v-model="taskFilter" aria-label="任务状态筛选">
                    <option value="all">全部状态</option>
                    <option value="running">生成中</option>
                    <option value="new">待执行</option>
                    <option value="queued">等待中</option>
                    <option value="detached">已断开</option>
                    <option value="unknown">状态未知</option>
                    <option value="submitting">提交中</option>
                    <option value="downloading">保存结果</option>
                    <option value="completed">已完成</option>
                    <option value="cancelled">已取消</option>
                    <option value="failed">失败</option>
                  </select>
                </div>
                <div v-if="!tasks.length" class="empty-state">
                  <ListTodo :size="30" />
                  <h3>这里还没有任务</h3>
                  <p>生成进度、取消结果和恢复记录会显示在这里。</p>
                </div>
                <div v-for="t in tasks" :key="t.id" class="task-row" :data-testid="`task-${t.id}`">
                  <span class="task-type"
                    ><Clapperboard v-if="t.kind === 'video'" :size="19" /><ImagePlus
                      v-else
                      :size="19"
                  /></span>
                  <div class="task-main">
                    <strong>{{ t.targetName }}</strong>
                    <p>
                      {{ t.kind === 'video' ? '视频生成' : '图片生成' }}<span> {{ t.time }}</span>
                    </p>
                    <span v-if="t.error" class="danger text-xs">{{ t.error }}</span>
                    <div v-if="t.results.length" class="task-output-grid">
                      <button
                        v-for="(result, i) in t.results"
                        :key="result.id"
                        class="task-output"
                        :aria-label="`查看${t.targetName}生成结果${i + 1}`"
                        @click="openPreview(result)"
                      >
                        <MediaThumb :media="result.media" :label="`${t.targetName}本次生成结果`" />
                        <span>{{ result.kind === 'video' ? '视频' : '图片' }} {{ i + 1 }}</span>
                      </button>
                    </div>
                  </div>
                  <div class="task-row-status">
                    <span
                      class="status-pill"
                      :class="{
                        completed: t.status === 'completed',
                        error: t.status === 'failed',
                      }"
                      >{{ statusNames[t.status] }}
                    </span>
                    <TaskProgress :task="t" :paused="store.paused" />
                  </div>
                  <button
                    v-if="['new', 'running', 'queued', 'cancel_requested'].includes(t.status)"
                    class="btn"
                    @click="store.cancelTask(t.id)"
                  >
                    取消</button
                  ><button
                    v-else-if="t.status === 'completed'"
                    class="btn"
                    @click="openTaskHistory(t)"
                  >
                    查看结果</button
                  ><button
                    v-else-if="['unknown', 'detached', 'queued', 'running'].includes(t.status)"
                    class="btn"
                    @click="store.resumeTask(t.id)"
                  >
                    <RotateCcw :size="13" />恢复查询</button
                  ><button
                    v-if="
                      (t.raw as { prompt_id?: string }).prompt_id &&
                      store.state?.activeJob !== t.id &&
                      ['queued', 'running', 'failed', 'cancel_requested'].includes(t.status)
                    "
                    class="btn"
                    @click="store.resumeTask(t.id)"
                  >
                    恢复查询</button
                  ><button
                    v-if="
                      ![
                        'new',
                        'submitting',
                        'running',
                        'queued',
                        'downloading',
                        'cancel_requested',
                      ].includes(t.status)
                    "
                    class="btn"
                    @click="openGenerate(t.targetId, t.kind, undefined, t.generation)"
                  >
                    再次生成
                  </button>
                  <details class="task-details">
                    <summary>生成详情</summary>
                    <p class="task-description">{{ t.prompt }}</p>
                    <GenerationDetails
                      :generation="t.generation"
                      :materials="(t.raw as { materials?: unknown[] }).materials"
                    /><ReferenceImages :files="t.generation.references" /><button
                      v-for="(result, i) in t.results"
                      :key="result.id"
                      class="text-action"
                      @click="store.openFile(result.file)"
                    >
                      打开{{ result.kind === 'video' ? '视频' : '图片' }}原文件 {{ i + 1 }}
                    </button>
                  </details>
                </div>
              </div>
            </template>
            <template v-else-if="store.page === 'settings'"><SettingsPanel /></template>
          </div>
        </div>
        <TimelinePanel v-if="store.page === 'shots'" @locate="locate" />
        <footer v-else class="workspace-bottom">
          <span>XY Studio · v{{ store.state?.version }}</span
          ><span>{{ store.project.name }} / 项目文件存储</span>
        </footer>
      </main>
      <button
        v-if="store.assistantOpen"
        class="assistant-backdrop"
        aria-label="关闭 AI 抽屉"
        @click="store.assistantOpen = false"
      /><AssistantPanel v-if="store.assistantOpen" @review="review" /><button
        v-else
        class="assistant-rail"
        aria-label="展开 AI 助手"
        @click="store.assistantOpen = true"
      >
        <Sparkles :size="18" /><span>AI 助手</span>
      </button>
    </div>
    <div v-if="store.toast" class="toast" role="status">
      <CircleCheck :size="17" />{{ store.toast }}
    </div>

    <StudioDialog
      :open="modal === 'edit'"
      @update:open="(v) => !v && (modal = null)"
      :title="
        target && 'duration' in target
          ? '编辑镜头'
          : edit.kind === 'characters'
            ? '修改角色名称'
            : '修改场景名称'
      "
      ><form @submit.prevent="saveEdit" class="form-content">
        <label
          >名称<input v-model="edit.name" maxlength="100" placeholder="留空沿用素材名称" /></label
        ><label v-if="target && 'duration' in target"
          >描述<textarea
            v-model="edit.description"
            rows="5"
            placeholder="外观、性格，或环境的光线与氛围…"
          /></label
        ><label v-if="target && 'duration' in target"
          >镜头时长（秒）<input
            v-model.number="edit.duration"
            type="number"
            disabled
            title="真实视频时长由媒体或生成参数决定"
        /></label>
        <footer class="dialog-actions">
          <button type="button" class="btn" @click="modal = null">取消</button
          ><button class="btn btn-primary">
            {{ target ? '保存修改' : '确认创建' }}
          </button>
        </footer>
      </form></StudioDialog
    >
    <StudioDialog
      :open="modal === 'project'"
      @update:open="(v) => !v && (modal = null)"
      title="一个新的故事"
      ><form
        class="form-content"
        @submit.prevent="
          store.createProject(projectName.trim());
          modal = null;
        "
      >
        <label
          >项目名称<input
            v-model="projectName"
            required
            maxlength="100"
            placeholder="你的故事叫什么名字？"
        /></label>
        <footer class="dialog-actions">
          <button type="button" class="btn" @click="modal = null">取消</button
          ><button class="btn btn-primary">创建项目</button>
        </footer>
      </form></StudioDialog
    >
    <StudioDialog
      :open="modal === 'generate'"
      @update:open="(v) => !v && cancelGeneration()"
      :title="gen.mode.startsWith('h3') ? '生成视频 · 参数审阅' : '生成图片 · 参数审阅'"
      :description="`结果保存到${gen.mode.startsWith('h3') ? '视频库' : '图片库'}。满意后再手动添加到资产或分镜。`"
      ><form class="form-content" @submit.prevent="confirmGeneration">
        <div class="target-pill">
          <Link2 :size="14" />{{ gen.mode.startsWith('h3') ? '视频库' : '图片库'
          }}<span>生成后由你选用</span>
        </div>
        <GenerationForm v-model="gen" target-id="" />
        <footer class="dialog-actions">
          <button type="button" class="btn" @click="cancelGeneration">取消生成</button
          ><button class="btn btn-primary">加入生成队列</button>
        </footer>
      </form></StudioDialog
    >
    <StudioDialog
      :open="modal === 'pick'"
      @update:open="(v) => !v && (modal = null)"
      :title="
        target
          ? `为${target.name}添加${pickKind === 'image' ? '图片' : '视频'}`
          : edit.kind === 'characters'
            ? '添加角色'
            : '添加场景'
      "
      description="先选择满意的素材，确认后才添加。图库中的其他结果会保留。"
      wide
      ><MediaLibrary
        :kind="pickKind"
        choose-only
        :selected-file="pickFile"
        @choose="pick"
        @generate="libraryGenerate"
      />
      <div v-if="pickFile" class="chosen-media">
        <MediaThumb :media="pickPreview?.media" label="已选素材" /><span
          >已选择{{ pickKind === 'image' ? '图片' : '视频' }}</span
        ><button
          class="text-action"
          @click="
            pickFile = '';
            pickPreview = null;
          "
        >
          取消选择
        </button>
      </div>
      <label v-if="!target" class="form-label"
        >名称（可选）<input
          v-model="pickName"
          maxlength="100"
          aria-label="素材名称"
          placeholder="留空沿用所选图片的名称"
      /></label>
      <footer class="dialog-actions">
        <button class="btn" @click="modal = null">取消添加</button
        ><button class="btn btn-primary" :disabled="!pickFile" @click="savePick">确认添加</button>
      </footer></StudioDialog
    >
    <StudioDialog
      :open="modal === 'adopt'"
      @update:open="(v) => !v && (modal = null)"
      title="选用素材"
      description="选择这份素材在故事中的用途。原文件和生成记录继续留在素材库。"
      ><div class="form-content">
        <label
          >添加到<select v-model="adoptDestination" aria-label="素材用途">
            <template v-if="adoptKind === 'image'"
              ><option value="characters">角色资产</option>
              <option value="scenes">场景资产</option></template
            >
            <option value="shot">分镜</option>
          </select></label
        ><label v-if="adoptDestination !== 'shot'"
          >名称（可选）<input
            v-model="pickName"
            maxlength="100"
            aria-label="选用素材名称"
            placeholder="留空沿用图片名称" /></label
        ><label v-else
          >分镜<select v-model="adoptShot" aria-label="选用到分镜">
            <option value="">请选择分镜</option>
            <option v-for="shot in store.project.shots" :key="shot.id" :value="shot.id">
              {{ shot.numberName }} · {{ shot.name }}
            </option>
          </select></label
        >
        <p v-if="adoptDestination === 'shot' && !store.project.shots.length" class="muted">
          还没有分镜，请先在分镜工作区添加镜头。
        </p>
        <footer class="dialog-actions">
          <button class="btn" @click="modal = null">取消选用</button
          ><button
            class="btn btn-primary"
            :disabled="adoptDestination === 'shot' && !adoptShot"
            @click="saveAdopt"
          >
            确认选用
          </button>
        </footer>
      </div></StudioDialog
    >
    <StudioDialog
      :open="modal === 'link'"
      @update:open="(v) => !v && (modal = null)"
      title="关联角色与场景"
      ><div class="link-picker">
        <label
          v-for="asset in store.project.assets"
          :key="asset.id"
          class="link-option"
          :class="{ selected: selectedLinks.includes(asset.id) }"
          ><MediaThumb
            :media="asset.versions.find((v) => v.id === asset.current)?.media"
            :label="asset.name" />
          <div>
            <strong>{{ asset.name }}</strong
            ><small>{{ asset.kind === 'characters' ? '角色' : '场景' }}</small>
          </div>
          <input v-model="selectedLinks" type="checkbox" :value="asset.id"
        /></label>
        <p v-if="!store.project.assets.length" class="empty-state">
          先从图片库添加一个角色或场景，再与镜头建立关联。
        </p>
      </div>
      <footer class="dialog-actions">
        <button class="btn" @click="modal = null">取消</button
        ><button class="btn btn-primary" @click="saveLinks">保存关联</button>
      </footer></StudioDialog
    >
    <StudioDialog
      :open="modal === 'history'"
      @update:open="(v) => !v && (modal = null)"
      :title="`${historyTask?.targetName || target?.name || '素材'} · 生成历史`"
      wide
      ><div v-if="!historyVersions.length" class="empty-state">
        <History :size="32" />
        <h3>每次尝试，都会留在这里</h3>
        <p>生成新版本后，可随时比较和重新选定。</p>
      </div>
      <div class="version-grid">
        <article v-for="v in historyVersions" :key="v.id" class="version-card">
          <button
            :aria-label="`查看${v.kind === 'video' ? '视频' : '图片'}历史大图`"
            @click="openPreview(v)"
          >
            <MediaThumb :media="v.media" :label="v.label" />
          </button>
          <div class="flex items-center justify-between mt-3">
            <h3>{{ v.label }}</h3>
            <span class="muted text-xs">{{ v.kind === 'image' ? '图片' : '视频' }}</span>
          </div>
          <p>{{ v.time }}</p>
          <button type="button" class="btn" @click="openAdopt(v.file, v.kind)">选用素材</button
          ><button
            v-if="v.generation"
            type="button"
            class="btn"
            @click="openGenerate('', v.kind, undefined, v.generation)"
          >
            再次生成
          </button>
          <p class="version-prompt">{{ v.prompt }}</p>
          <details class="version-details">
            <summary>生成参数与使用素材</summary>
            <GenerationDetails
              :generation="v.generation"
              :materials="v.materials"
            /><ReferenceImages v-if="v.generation" :files="v.generation.references" />
          </details>
          <button
            v-if="target?.versions.some((version) => version.id === v.id)"
            class="btn"
            :class="{
              active:
                target &&
                ('current' in target
                  ? target.current === v.id
                  : target.imageVersion === v.id || target.videoVersion === v.id),
            }"
            @click="store.useVersion(targetId, v.id)"
          >
            设为当前版本
          </button>
        </article>
      </div>
      <details v-if="pendingRecords.length" class="version-details">
        <summary>未完成记录 · {{ pendingRecords.length }}</summary>
        <div v-for="t in pendingRecords" :key="t.id">
          <p>{{ statusNames[t.status] }} · {{ t.time }} · {{ t.error }}</p>
          <pre>{{ t.prompt }}</pre>
        </div>
      </details></StudioDialog
    >
    <StudioDialog
      :open="modal === 'review'"
      @update:open="(v) => !v && (modal = null)"
      :title="suggestion?.title || '审阅 AI 操作'"
      description="请检查以下内容，确认后才修改项目。取消不会执行这次操作。"
      ><ReferenceImages v-if="suggestion?.args.file" :files="[String(suggestion.args.file)]" />
      <dl class="review-fields">
        <div v-for="field in reviewDetails" :key="field.label">
          <dt>{{ field.label }}</dt>
          <dd><MessageText :text="field.text" /></dd>
        </div>
      </dl>
      <footer class="dialog-actions">
        <button
          class="btn"
          @click="
            suggestion && store.reviewSuggestion(suggestion, false);
            modal = null;
          "
        >
          取消本次操作</button
        ><button
          class="btn btn-primary"
          @click="
            suggestion && store.reviewSuggestion(suggestion, true);
            modal = null;
          "
        >
          确认{{ suggestion?.title }}
        </button>
      </footer></StudioDialog
    >
    <StudioDialog
      :open="modal === 'delete'"
      @update:open="(v) => !v && (modal = null)"
      title="删除条目"
      description="文件和历史输出仍保留，相关镜头解除素材关联。"
      ><p>确认删除「{{ target?.name }}」？</p>
      <footer class="dialog-actions">
        <button class="btn" @click="modal = null">保留条目</button
        ><button class="btn btn-primary" @click="deleteTarget">确认删除</button>
      </footer></StudioDialog
    >
    <StudioDialog
      :open="modal === 'preview'"
      @update:open="(v) => !v && (modal = null)"
      title="素材预览"
      description="项目原始素材 · 等比预览与缩放"
      wide
      ><div class="preview-toolbar">
        <button class="icon-btn" aria-label="缩小图片" @click="zoom = Math.max(0.5, zoom - 0.25)">
          <ZoomOut :size="18" /></button
        ><span>{{ Math.round(zoom * 100) }}%</span
        ><button class="icon-btn" aria-label="放大图片" @click="zoom = Math.min(3, zoom + 0.25)">
          <ZoomIn :size="18" /></button
        ><button class="btn" @click="zoom = 1">适应窗口</button>
      </div>
      <button v-if="preview" class="btn mb-3" @click="store.openFile(preview.file)">
        打开原文件
      </button>
      <div class="large-preview">
        <VideoPreview
          v-if="preview?.kind === 'video'"
          :notice="preview.error"
          :media="preview.media"
          :url="preview.url"
          :file="preview.file"
          @fallback="store.openFile"
          :duration="0"
          label="视频预览"
        /><MediaThumb
          v-else
          :media="preview?.media"
          label="大图预览"
          :style="{ width: `${zoom * 100}%`, minWidth: `${zoom * 100}%` }"
        /></div
    ></StudioDialog>
  </div>
</template>
