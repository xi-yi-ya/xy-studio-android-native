import { computed, ref } from 'vue';
import { defineStore } from 'pinia';
import { connect, command } from '../gateway';
import type {
  Asset,
  Generation,
  Page,
  ProjectState,
  State,
  Suggestion,
  Version,
  LibraryResult,
} from '../types';
const empty: ProjectState = {
  id: '',
  name: '打开一个故事',
  root: '',
  story: '',
  updated: '',
  assets: [],
  shots: [],
  tasks: [],
  chat: [],
  paused: false,
};
export const useStudio = defineStore('studio', () => {
  const state = ref<State | null>(null),
    connectionError = ref(''),
    ready = ref(false),
    page = ref<Page>('projects');
  const assistantOpen = ref(true),
    toast = ref(''),
    persistenceError = ref('');
  const collapsed = new Map<string, boolean>();
  const project = computed(() => state.value?.project || empty);
  const hasProject = computed(() => !!state.value?.project);
  const projects = computed(
    () =>
      state.value?.recent.map((r) => ({
        id: r.path,
        name: r.title,
        story: r.path,
        updated: '',
        shots: [],
      })) || [],
  );
  const selectedId = computed(() => state.value?.selectedId || null);
  const selection = computed(
    () =>
      project.value.shots.find((s) => s.id === selectedId.value) ||
      project.value.assets.find((a) => a.id === selectedId.value) ||
      null,
  );
  const model = computed({
    get: () => state.value?.config.model || '',
    set: (value) => {
      void api('settings.save', { model: value }).catch(() => {});
    },
  });
  const online = computed({
    get: () => state.value?.config.online || false,
    set: (value) => {
      void api('settings.save', { online: value }).catch(() => {});
    },
  });
  const paused = computed(() => project.value.paused),
    busy = computed(() => state.value?.busy || false);
  const totalDuration = computed(() =>
    Number(project.value.shots.reduce((n, s) => n + s.duration, 0).toFixed(2)),
  );
  const pendingTasks = computed(
    () =>
      project.value.tasks.filter((t) =>
        ['new', 'queued', 'submitting', 'running', 'downloading', 'cancel_requested'].includes(
          t.status,
        ),
      ).length,
  );
  let toastTimer: ReturnType<typeof setTimeout>;
  function notify(text: string) {
    toast.value = text;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (toast.value = ''), 6000);
  }
  function receive(value: unknown) {
    const next = value as State;
    if (next.project)
      next.project.shots.forEach((s) => (s.collapsed = collapsed.get(s.id) || false));
    state.value = next;
    ready.value = true;
  }
  async function api<T = unknown>(name: string, payload: Record<string, unknown> = {}): Promise<T> {
    try {
      return await command<T>(name, payload);
    } catch (e) {
      notify(String(e));
      throw e;
    }
  }
  async function initialize() {
    try {
      receive(await connect(receive, notify));
      if (hasProject.value) page.value = 'shots';
    } catch (e) {
      connectionError.value = String(e);
    }
  }
  function fold(id: string, value: boolean) {
    collapsed.set(id, value);
    const s = project.value.shots.find((s) => s.id === id);
    if (s) s.collapsed = value;
  }
  function select(id: string | null) {
    void api('selection', { id }).catch(() => {});
  }
  function toggleSelection(id: string) {
    void api('selection', { id, toggle: true }).catch(() => {});
  }
  function clearContext() {
    return api('context.clear');
  }
  function removeContext(id: string) {
    return api('context.remove', { id });
  }
  function removeMediaContext(file: string) {
    return api('context.remove', { file });
  }
  async function pinMedia(file: string) {
    await api('context.add_media', { file });
    assistantOpen.value = true;
    notify('已添加到下一条消息的素材引用');
  }
  function queryLibrary(kind: 'image' | 'video', query: Record<string, unknown> = {}) {
    return api<LibraryResult>('library.query', { kind, ...query });
  }
  function previewMedia(file: string) {
    return api<Version>('library.preview', { file });
  }
  function importMedia(paths?: string[], kind: 'image' | 'video' | 'auto' = 'auto') {
    return api<string[]>('library.import', { kind, ...(paths ? { paths } : {}) });
  }
  function addFromMedia(kind: Asset['kind'], file: string, name = '') {
    return api<string>('asset.from_media', { kind, file, name });
  }
  function useMedia(id: string, file: string) {
    return api('asset.use_media', { id, file });
  }
  function rename(id: string, name: string) {
    return api('asset.rename', { id, name });
  }
  function pin(id: string) {
    assistantOpen.value = true;
    void api('selection', { id, pin: true }).catch(() => {});
  }
  async function openProject(path?: string) {
    const result = await api('project.open', path ? { path } : {});
    if (result) page.value = 'shots';
  }
  async function createProject(name: string) {
    const result = await api('project.new', { title: name });
    if (result) page.value = 'shots';
  }
  async function newShot() {
    return api<string>('asset.add', { kind: 'shots', name: '', description: '' });
  }
  async function addAsset(kind: Asset['kind'], name: string, description: string) {
    return api('asset.add', { kind, name, description });
  }
  function editAsset(id: string, name: string, description: string) {
    return api('asset.update', { id, name, description });
  }
  function link(id: string, ids: string[]) {
    return api('asset.link', { id, ids });
  }
  function remove(id: string) {
    return api('asset.delete', { id });
  }
  function importImage(id: string) {
    return api('asset.import', { id });
  }
  function useVersion(id: string, version: string) {
    return api('version.use', { id, version });
  }
  function taskStatus(id: string) {
    const tasks = project.value.tasks.filter((t) => t.targetId === id);
    return (
      tasks.find((t) => t.id === state.value?.activeJob) ||
      tasks.find((t) =>
        ['new', 'submitting', 'queued', 'running', 'downloading', 'cancel_requested'].includes(
          t.status,
        ),
      ) ||
      tasks.at(-1)
    );
  }
  function defaults(target = '', mode?: string, kind: 'image' | 'video' = 'image') {
    return api<Generation>('generation.defaults', { target, ...(mode ? { mode } : {}), kind });
  }
  function queueGeneration(target: string, generation: Generation) {
    return api<string>('generation.submit', { target, generation });
  }
  function toggleQueue() {
    return api('queue.toggle');
  }
  function cancelTask(id: string) {
    return api('task.cancel', { id });
  }
  function resumeTask(id: string) {
    return api('task.resume', { id });
  }
  function sendChat(text: string) {
    return api('chat.send', { text });
  }
  function reviewSuggestion(s: Suggestion, accepted: boolean, generation?: Generation) {
    return api('review.respond', { id: s.id, accepted, ...(generation ? { generation } : {}) });
  }
  function save() {
    return api('project.save');
  }
  function saveStory(text: string) {
    return api('project.story', { text });
  }
  function refreshModels() {
    return api('models.refresh');
  }
  function saveSettings(value: Record<string, unknown>) {
    return api('settings.save', value);
  }
  function openLink(url: string) {
    return api('link.open', { url });
  }
  function folder() {
    return api('project.folder');
  }
  function importAgent() {
    return api('agent.import');
  }
  function openFile(file: string) {
    return api('media.open', { file });
  }
  function reviewed(id: string) {
    return api('asset.reviewed', { id });
  }
  return {
    state,
    connectionError,
    ready,
    page,
    project,
    hasProject,
    projects,
    assistantOpen,
    selectedId,
    selection,
    model,
    online,
    paused,
    busy,
    totalDuration,
    pendingTasks,
    toast,
    persistenceError,
    notify,
    api,
    initialize,
    fold,
    select,
    toggleSelection,
    clearContext,
    removeContext,
    removeMediaContext,
    pinMedia,
    queryLibrary,
    previewMedia,
    importMedia,
    addFromMedia,
    useMedia,
    rename,
    pin,
    openProject,
    createProject,
    newShot,
    addAsset,
    editAsset,
    link,
    remove,
    importImage,
    useVersion,
    taskStatus,
    defaults,
    queueGeneration,
    toggleQueue,
    cancelTask,
    resumeTask,
    sendChat,
    reviewSuggestion,
    save,
    saveStory,
    refreshModels,
    saveSettings,
    openLink,
    folder,
    importAgent,
    openFile,
    reviewed,
  };
});
