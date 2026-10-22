<script setup lang="ts">
import { ref, computed, watch, onBeforeUnmount } from 'vue';
import {
  Search,
  RefreshCw,
  Image,
  Film,
  ArrowLeft,
  ArrowRight,
  Send,
  ExternalLink,
  Focus,
  Trash2,
  RotateCcw,
} from 'lucide-vue-next';
import type { LibraryAsset, LibraryResult, Version, Generation } from '../types';
import { useStudio } from '../stores/studio';
import MediaThumb from './MediaThumb.vue';
import MessageText from './MessageText.vue';
import StudioDialog from './StudioDialog.vue';
import ReferenceImages from './ReferenceImages.vue';
import GenerationDetails from './GenerationDetails.vue';
const props = defineProps<{
  kind: 'image' | 'video';
  chooseOnly?: boolean;
  selectedFile?: string;
}>();
const emit = defineEmits<{
  preview: [v: Version];
  locate: [id: string];
  choose: [file: string];
  generate: [kind: 'image' | 'video', previous?: Generation];
  adopt: [file: string, kind: 'image' | 'video'];
}>();
const store = useStudio();
const query = ref(''),
  source = ref('all'),
  owner = ref('all'),
  sort = ref('newest'),
  offset = ref(0);
const result = ref<LibraryResult>(),
  loading = ref(false),
  error = ref(''),
  detail = ref<LibraryAsset | null>(null),
  detailGeneration = ref<Generation>();
const size = computed(() => (props.chooseOnly ? 12 : 24));
const trash = ref(false),
  deleting = ref<LibraryAsset | null>(null),
  deletingBusy = ref(false),
  deleteError = ref('');
function toggleTrash() {
  trash.value = !trash.value;
  query.value = '';
  source.value = 'all';
  owner.value = 'all';
}
function askDelete(item: LibraryAsset) {
  deleting.value = item;
  deleteError.value = '';
}
async function deleteMedia() {
  if (!deleting.value || deletingBusy.value) return;
  deletingBusy.value = true;
  try {
    await store.api('library.delete', { file: deleting.value.file });
    deleting.value = null;
    detail.value = null;
    await load();
    store.notify('素材已移入回收站，可以恢复；历史记录保留');
  } catch (e) {
    deleteError.value = String(e);
  } finally {
    deletingBusy.value = false;
  }
}
async function restore(item: LibraryAsset) {
  await store.api('library.restore', { file: item.file });
  await load();
  store.notify('素材已恢复到' + labels.value + '库');
}
const sourceNames: Record<string, string> = {
  imported: '导入素材',
  generated: '生成素材',
  project: '项目原文件',
};
const labels = computed(() => (props.kind === 'image' ? '图片' : '视频'));
let serial = 0,
  timer: ReturnType<typeof setTimeout> | undefined;
async function load() {
  const version = ++serial;
  loading.value = true;
  error.value = '';
  try {
    const data = await store.queryLibrary(props.kind, {
      query: query.value,
      source: source.value,
      owner: owner.value,
      sort: sort.value,
      offset: offset.value,
      limit: size.value,
      trash: trash.value,
    });
    if (version !== serial) return;
    if (data.total && offset.value >= data.total) {
      offset.value = Math.floor((data.total - 1) / size.value) * size.value;
      return;
    }
    result.value = data;
  } catch (e) {
    if (version === serial) error.value = String(e);
  } finally {
    if (version === serial) loading.value = false;
  }
}
function refresh() {
  void load();
}
async function importMedia() {
  await store.api('library.import', { kind: props.kind });
  offset.value = 0;
  refresh();
}
watch(
  [query, source, owner, sort, trash, () => props.kind, () => store.project.id],
  () => {
    offset.value = 0;
    detail.value = null;
    clearTimeout(timer);
    serial++;
    timer = setTimeout(load, 160);
  },
  { immediate: true },
);
watch(offset, refresh);
watch(
  () => store.project.tasks.map((t) => `${t.id}:${t.status}:${t.results.length}`).join('|'),
  () => {
    clearTimeout(timer);
    timer = setTimeout(load, 160);
  },
);
onBeforeUnmount(() => {
  serial++;
  clearTimeout(timer);
});
async function preview(item: LibraryAsset) {
  emit('preview', await store.previewMedia(item.file));
  detail.value = null;
}
function date(value: string) {
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? '时间未记录'
    : d.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      });
}
function bytes(value: number | null) {
  return value === null
    ? '大小未知'
    : value >= 1048576
      ? `${(value / 1048576).toFixed(1)} MB`
      : `${Math.ceil(value / 1024)} KB`;
}
function locate(id: string) {
  detail.value = null;
  emit('locate', id);
}
function choose(item: LibraryAsset) {
  emit('choose', item.file);
}
async function details(item: LibraryAsset) {
  detail.value = item;
  detailGeneration.value = undefined;
  const v = await store.previewMedia(item.file);
  if (detail.value?.file === item.file) detailGeneration.value = v.generation;
}
async function again(item: LibraryAsset) {
  const v = await store.previewMedia(item.file);
  if (!v.generation) {
    store.notify('这份导入素材没有生成参数，可以基于图片继续编辑');
    return;
  }
  detail.value = null;
  emit('generate', item.kind, v.generation);
}
async function derive(item: LibraryAsset, video = false) {
  const g = await store.defaults('', video ? 'h3_i2v' : 'qwen_edit');
  g.references = [item.file];
  g.prompt = '';
  detail.value = null;
  emit('generate', video ? 'video' : 'image', g);
}
</script>
<template>
  <section
    class="media-library"
    :class="{ 'choose-library': chooseOnly }"
    :aria-label="`${labels}素材库`"
  >
    <div class="library-intro surface" v-if="!chooseOnly">
      <div>
        <strong
          >{{ trash ? '回收站 · ' : '全部' }}{{ labels }} · {{ result?.stats.all || 0 }}</strong
        ><span
          >生成 {{ result?.stats.generated || 0 }} · 导入 {{ result?.stats.imported || 0 }} · 其他
          {{ result?.stats.project || 0 }}</span
        >
      </div>
      <p>
        生成和导入的素材统一保存在这里。预览满意后，再添加到角色、场景或分镜。使用“导入”按钮添加本机图片或视频。
      </p>
    </div>
    <div class="library-filters">
      <label class="search-field"
        ><Search :size="15" /><input
          v-model="query"
          :aria-label="`搜索${labels}资产`"
          placeholder="搜索名称、关联对象或生成提示词…"
      /></label>
      <select v-model="source" :aria-label="`${labels}来源筛选`">
        <option value="all">全部来源</option>
        <option value="generated">生成素材</option>
        <option value="imported">导入素材</option>
        <option value="project">其他项目文件</option>
      </select>
      <select v-model="owner" :aria-label="`${labels}归属筛选`">
        <option value="all">全部归属</option>
        <option value="characters">角色</option>
        <option value="scenes">场景</option>
        <option value="shots">分镜</option>
        <option value="unassigned">未关联</option>
        <option value="deleted">条目已删除</option>
      </select>
      <select v-model="sort" :aria-label="`${labels}排序`">
        <option value="newest">最新在前</option>
        <option value="oldest">最早在前</option>
        <option value="name">按名称</option>
      </select>
      <button class="btn" :disabled="loading" :aria-label="`刷新${labels}库`" @click="refresh">
        <RefreshCw :size="14" />刷新
      </button>
      <button v-if="!trash" class="btn" :aria-label="`导入${labels}到素材库`" @click="importMedia">
        导入{{ labels }}
      </button>
      <button v-if="!chooseOnly" class="btn" @click="toggleTrash">
        <Trash2 :size="14" />{{ trash ? `返回${labels}库` : '回收站' }}
      </button>
    </div>
    <p v-if="loading" class="library-feedback">正在查询{{ labels }}资产…</p>
    <div v-if="error" class="error-banner">
      {{ error }}<button class="text-action" @click="refresh">重新查询</button>
    </div>
    <div v-if="result && !result.total && !loading" class="empty-state surface">
      <Image v-if="kind === 'image'" :size="32" /><Film v-else :size="32" />
      <h3>
        {{
          result.stats.all
            ? `没有找到匹配的${labels}`
            : trash
              ? `回收站暂无${labels}`
              : `${labels}库还没有${labels}`
        }}
      </h3>
      <p>
        {{
          result.stats.all
            ? '试试其他关键词或清除筛选条件。'
            : trash
              ? '删除的素材会出现在这里，可恢复到素材库。'
              : `请先生成或导入${labels}，再选择添加。`
        }}
      </p>
      <button
        v-if="!result.stats.all && !trash"
        type="button"
        class="btn btn-primary"
        @click="emit('generate', kind)"
      >
        生成{{ labels }}</button
      ><button
        v-if="query || source !== 'all' || owner !== 'all'"
        class="btn"
        @click="
          query = '';
          source = 'all';
          owner = 'all';
        "
      >
        清除筛选
      </button>
    </div>
    <div class="library-grid" v-if="result">
      <article
        v-for="item in result.items"
        :key="item.id"
        class="library-card surface"
        :class="{ selected: item.file === selectedFile }"
        :data-testid="`library-${item.id}`"
      >
        <button
          class="library-image"
          :disabled="trash || !item.exists || !!item.error"
          :aria-label="`${chooseOnly ? '选用' : '查看'}${item.name}`"
          @click="chooseOnly ? choose(item) : preview(item)"
        >
          <MediaThumb :media="item.media" :label="item.error || item.name" /><span
            v-if="item.kind === 'video'"
            class="library-video-badge"
            ><Film :size="13" />{{
              item.duration === null ? '视频' : `${item.duration.toFixed(2)} 秒`
            }}</span
          >
        </button>
        <div class="library-card-content">
          <h3 :title="item.name">{{ item.name }}</h3>
          <div class="library-badges">
            <span>{{ sourceNames[item.source] }}</span
            ><span v-if="item.current">当前版本</span
            ><span v-else-if="item.owners.length">历史版本</span
            ><span v-if="item.deletedOwner">条目已删除</span>
          </div>
          <p>
            {{ item.width && item.height ? `${item.width} × ${item.height}` : '尺寸未取得' }} ·
            {{ bytes(item.bytes) }}
          </p>
          <p v-if="item.error" class="danger">{{ item.error }}</p>
          <p v-else>{{ date(item.time) }}</p>
        </div>
        <footer v-if="trash">
          <button class="btn" :disabled="!item.exists" @click="restore(item)">
            <RotateCcw :size="13" />恢复素材
          </button>
        </footer>
        <footer v-else-if="chooseOnly">
          <button class="btn" :disabled="!item.exists || !!item.error" @click="choose(item)">
            选用这{{ kind === 'image' ? '张图片' : '段视频' }}</button
          ><button
            type="button"
            class="text-action"
            :disabled="!item.exists || !!item.error"
            @click="details(item)"
          >
            预览与记录
          </button>
        </footer>
        <footer v-else>
          <button
            type="button"
            class="text-action"
            :disabled="!item.exists || !!item.error"
            @click="emit('adopt', item.file, item.kind)"
          >
            选用素材</button
          ><button class="text-action" @click="details(item)">查看记录</button
          ><button
            class="text-action"
            :disabled="!item.exists || !!item.error"
            @click="store.pinMedia(item.file)"
          >
            <Send :size="12" />发送给 AI
          </button>
          <button
            type="button"
            class="text-action danger"
            :aria-label="`删除素材 ${item.name}`"
            @click="askDelete(item)"
          >
            <Trash2 :size="12" />删除
          </button>
        </footer>
      </article>
    </div>
    <div v-if="result && result.total" class="library-pagination">
      <span
        >共 {{ result.total }} 项 · {{ offset + 1 }}–{{
          Math.min(offset + size, result.total)
        }}</span
      >
      <div>
        <button
          class="btn"
          :disabled="offset === 0 || loading"
          :aria-label="`${labels}上一页`"
          @click="offset = Math.max(0, offset - size)"
        >
          <ArrowLeft :size="13" />上一页</button
        ><button
          class="btn"
          :disabled="!result.hasMore || loading"
          :aria-label="`${labels}下一页`"
          @click="offset += size"
        >
          下一页<ArrowRight :size="13" />
        </button>
      </div>
    </div>
  </section>
  <StudioDialog
    :open="!!deleting"
    @update:open="(v) => !v && !deletingBusy && (deleting = null)"
    title="删除素材"
    description="移入项目回收站，原文件与历史记录保留，可恢复。此操作不释放磁盘空间。"
  >
    <p>将「{{ deleting?.name }}」移入回收站？</p>
    <p v-if="deleting?.current" class="danger">
      这份素材正在被角色、场景或分镜使用，请先替换或移除对应条目的图片/视频。
    </p>
    <p v-if="deleteError" class="danger" role="alert">{{ deleteError }}</p>
    <footer class="dialog-actions">
      <button class="btn" :disabled="deletingBusy" @click="deleting = null">保留素材</button
      ><button
        class="btn btn-primary"
        :disabled="deletingBusy || deleting?.current"
        @click="deleteMedia"
      >
        移入回收站
      </button>
    </footer>
  </StudioDialog>
  <StudioDialog
    :open="!!detail"
    @update:open="(v) => !v && (detail = null)"
    :title="detail?.name || '素材详情'"
  >
    <template v-if="detail"
      ><MediaThumb class="library-detail-image" :media="detail.media" :label="detail.name" />
      <dl class="review-fields">
        <div>
          <dt>素材来源</dt>
          <dd>
            {{ sourceNames[detail.source] }} ·
            {{ detail.current ? '当前版本' : '保留的历史或独立素材' }}
          </dd>
        </div>
        <div>
          <dt>尺寸与大小</dt>
          <dd>
            {{
              detail.width && detail.height ? `${detail.width} × ${detail.height}` : '尺寸未取得'
            }}
            · {{ bytes(detail.bytes)
            }}<span v-if="detail.duration !== null"> · {{ detail.duration.toFixed(2) }} 秒</span>
          </dd>
        </div>
        <div>
          <dt>记录时间</dt>
          <dd>{{ date(detail.time) }}</dd>
        </div>
        <div>
          <dt>关联对象</dt>
          <dd v-if="detail.owners.length">
            <button v-for="o in detail.owners" :key="o.id" class="btn" @click="locate(o.id)">
              <Focus :size="13" />{{ o.name }}
            </button>
          </dd>
          <dd v-else>
            {{
              detail.deletedOwner ? '原条目已删除，生成文件仍保留' : '尚未关联到角色、场景或分镜'
            }}
          </dd>
        </div>
        <div v-if="detail.prompt">
          <dt>本次生成提示词</dt>
          <dd><MessageText :text="detail.prompt" /></dd>
        </div>
      </dl>
      <GenerationDetails v-if="detailGeneration" :generation="detailGeneration" /><ReferenceImages
        v-if="detailGeneration"
        :files="detailGeneration.references"
      />
      <div class="library-derive">
        <button v-if="detailGeneration" type="button" class="btn" @click="again(detail)">
          再次生成</button
        ><template v-if="detail.kind === 'image'"
          ><button type="button" class="btn" @click="derive(detail)">基于此图继续编辑</button
          ><button type="button" class="btn" @click="derive(detail, true)">
            用此图生成视频
          </button></template
        >
      </div>
      <p v-if="detail.error" class="danger">{{ detail.error }}</p>
      <footer class="dialog-actions">
        <button class="btn" :disabled="!detail.exists" @click="store.openFile(detail.file)">
          <ExternalLink :size="14" />打开原文件</button
        ><button class="btn" :disabled="!detail.exists" @click="preview(detail)">放大预览</button
        ><button
          class="btn btn-primary"
          :disabled="!detail.exists"
          @click="store.pinMedia(detail.file)"
        >
          发送给 AI
        </button>
      </footer></template
    >
  </StudioDialog>
</template>
