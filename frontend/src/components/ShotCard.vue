<script setup lang="ts">
import { computed, ref } from 'vue';
import {
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Pencil,
  Plus,
  X,
  History,
  ImagePlus,
  Clapperboard,
  Send,
  Trash2,
  Check,
  Link2,
} from 'lucide-vue-next';
import {
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuPortal,
  DropdownMenuContent,
  DropdownMenuItem,
} from 'reka-ui';
import type { Shot, Version } from '../types';
import { useStudio } from '../stores/studio';
import MediaThumb from './MediaThumb.vue';
import VideoPreview from './VideoPreview.vue';
import TaskProgress from './TaskProgress.vue';
const props = defineProps<{ shot: Shot; index: number }>();
const emit = defineEmits<{
  edit: [id: string];
  delete: [id: string];
  choose: [id: string, kind: 'image' | 'video'];
  link: [id: string];
  preview: [version: Version];
}>();
const store = useStudio();
const history = ref<'image' | 'video' | null>(null);
const currentImage = computed(() =>
  props.shot.versions.find((v) => v.id === props.shot.imageVersion),
);
const currentVideo = computed(() =>
  props.shot.versions.find((v) => v.id === props.shot.videoVersion),
);
const linked = computed(() =>
  props.shot.assetIds.map((id) => store.project.assets.find((a) => a.id === id)).filter((a) => !!a),
);
const task = computed(() => store.taskStatus(props.shot.id));
const status = computed(() =>
  task.value?.status === 'running'
    ? `生成中${task.value.progress === null ? '' : ' · ' + Math.round(task.value.progress) + '%'}`
    : ['new', 'submitting', 'queued'].includes(task.value?.status || '')
      ? '等待添加'
      : task.value?.status === 'cancelled'
        ? '已取消'
        : task.value?.status === 'failed'
          ? '生成失败'
          : props.shot.imageVersion
            ? '已完成'
            : '待制作',
);
function toggleHistory(kind: 'image' | 'video') {
  history.value = history.value === kind ? null : kind;
}
function selectCard(event: MouseEvent) {
  if (
    (event.target as HTMLElement).closest(
      'button, a, input, select, textarea, summary, video, [role="menuitem"]',
    )
  )
    return;
  store.toggleSelection(props.shot.id);
}
function previewImage() {
  if (!currentImage.value) return;
  store.select(props.shot.id);
  emit('preview', currentImage.value);
}
</script>
<template>
  <article
    class="shot-card surface"
    :class="{
      selected: store.selectedId === shot.id,
      collapsed: shot.collapsed,
    }"
    :id="`shot-${shot.id}`"
    :data-testid="`shot-${shot.id}`"
    @click="selectCard"
  >
    <header class="shot-header">
      <button class="shot-heading" @click.stop="store.toggleSelection(shot.id)">
        <span class="shot-number">SHOT {{ String(index + 1).padStart(2, '0') }}</span>
        <h3>{{ shot.name }}</h3>
      </button>
      <div class="flex items-center gap-3">
        <span
          class="status-pill"
          :class="{
            completed: status === '已完成',
            working: task?.status === 'running' && task.progress !== null,
            error: task?.status === 'failed',
          }"
          ><span class="status-dot" />{{ status }}</span
        ><span class="shot-duration">{{ shot.durationLabel }}</span>
        <DropdownMenuRoot
          ><DropdownMenuTrigger class="icon-btn" :aria-label="`镜头${index + 1}更多操作`"
            ><MoreHorizontal :size="19" /></DropdownMenuTrigger
          ><DropdownMenuPortal
            ><DropdownMenuContent class="menu-content" align="end"
              ><DropdownMenuItem class="menu-item" @select="emit('edit', shot.id)"
                ><Pencil :size="15" />编辑镜头</DropdownMenuItem
              ><DropdownMenuItem class="menu-item" @select="store.pin(shot.id)"
                ><Send :size="15" />发送给 AI</DropdownMenuItem
              ><DropdownMenuItem class="menu-item danger" @select="emit('delete', shot.id)"
                ><Trash2 :size="15" />删除镜头</DropdownMenuItem
              ></DropdownMenuContent
            ></DropdownMenuPortal
          ></DropdownMenuRoot
        >
        <button
          class="icon-btn"
          :aria-label="`${shot.collapsed ? '展开' : '折叠'}镜头${index + 1}`"
          :aria-expanded="!shot.collapsed"
          @click.stop="store.fold(shot.id, !shot.collapsed)"
        >
          <ChevronRight v-if="shot.collapsed" :size="18" /><ChevronDown v-else :size="18" />
        </button>
      </div>
    </header>
    <div v-if="!shot.collapsed" class="shot-body">
      <section class="shot-description">
        <div class="section-caption">
          镜头描述<button
            class="icon-btn"
            :aria-label="`编辑镜头${index + 1}`"
            @click.stop="emit('edit', shot.id)"
          >
            <Pencil :size="14" />
          </button>
        </div>
        <p :title="shot.description">
          {{ shot.description || '描述这个镜头里，故事如何发生。' }}
        </p>
        <div class="section-caption mt-5">
          使用素材 <span class="muted text-xs">{{ linked.length }}</span>
        </div>
        <div class="linked-assets">
          <div v-for="asset in linked" :key="asset.id" class="linked-item">
            <button
              class="linked-image"
              :class="{ selected: store.selectedId === asset.id }"
              :aria-label="`选择素材${asset.name}`"
              :aria-pressed="store.selectedId === asset.id"
              @click.stop="store.toggleSelection(asset.id)"
            >
              <MediaThumb
                :media="asset.versions.find((v) => v.id === asset.current)?.media"
                :label="asset.name"
              /></button
            ><button
              class="unlink"
              :aria-label="`解除${asset.name}关联`"
              @click.stop="
                store.link(
                  shot.id,
                  shot.assetIds.filter((id) => id !== asset.id),
                )
              "
            >
              <X :size="11" /></button
            ><span>{{ asset.name }}</span>
          </div>
          <button
            class="add-reference"
            :aria-label="`关联镜头${index + 1}素材`"
            @click.stop="emit('link', shot.id)"
          >
            <Plus :size="19" />
          </button>
        </div>
        <button class="text-action" @click.stop="emit('link', shot.id)">
          <Link2 :size="12" />管理素材关联
        </button>
        <div v-if="shot.references.length" class="actual-references">
          <span class="subtle-label">最近生成参考</span
          ><MediaThumb v-for="r in shot.references" :key="r.file" :media="r.url" :label="r.file" />
        </div>
        <button v-if="shot.needsReview" class="text-action" @click.stop="store.reviewed(shot.id)">
          素材已变化 · 确认已检查
        </button>
      </section>
      <section class="shot-media">
        <div class="section-caption">
          分镜图
          <span class="subtle-label">{{ currentImage ? '当前版本' : '等待添加' }}</span>
        </div>
        <button
          class="shot-image"
          :aria-label="`查看镜头${index + 1}分镜图`"
          :disabled="!currentImage"
          :aria-pressed="store.selectedId === shot.id"
          @click.stop="store.toggleSelection(shot.id)"
          @dblclick.stop="previewImage"
        >
          <MediaThumb :media="currentImage?.media" label="双击查看分镜大图" />
        </button>
        <div class="media-actions">
          <button class="btn btn-soft" @click.stop="emit('choose', shot.id, 'image')">
            <ImagePlus :size="15" />{{ currentImage ? '替换图片' : '添加图片' }}</button
          ><button
            class="btn"
            :class="{ active: history === 'image' }"
            @click.stop="toggleHistory('image')"
          >
            <History :size="14" />历史版本<span class="count">{{
              shot.versions.filter((v) => v.kind === 'image').length
            }}</span>
          </button>
        </div>
      </section>
      <section class="shot-media">
        <div class="section-caption">
          分镜视频
          <span class="subtle-label">{{ currentVideo ? shot.durationLabel : '等待添加' }}</span>
        </div>
        <VideoPreview
          :notice="currentVideo?.error"
          :media="currentVideo?.media"
          :url="currentVideo?.url"
          :file="currentVideo?.file"
          @fallback="store.openFile"
          :duration="shot.duration"
          :label="`${shot.name}视频`"
          @enlarge="currentVideo && emit('preview', currentVideo)"
        />
        <div class="media-actions">
          <button class="btn btn-soft" @click.stop="emit('choose', shot.id, 'video')">
            <Clapperboard :size="15" />{{ currentVideo ? '替换视频' : '添加视频' }}</button
          ><button
            class="btn"
            :class="{ active: history === 'video' }"
            @click.stop="toggleHistory('video')"
          >
            <History :size="14" />历史版本<span class="count">{{
              shot.versions.filter((v) => v.kind === 'video').length
            }}</span>
          </button>
        </div>
      </section>
    </div>
    <TaskProgress :task="task" :paused="store.paused" />
    <div v-if="history && !shot.collapsed" class="inline-history">
      <div class="flex items-center justify-between">
        <span class="section-caption"
          >{{ history === 'image' ? '分镜图' : '视频' }}版本 · 始终保留在此镜头中</span
        ><button class="icon-btn" aria-label="关闭镜头历史" @click.stop="history = null">
          <X :size="15" />
        </button>
      </div>
      <p v-if="!shot.versions.some((v) => v.kind === history)" class="muted py-5">
        还没有选用记录，请从素材库添加满意的版本。
      </p>
      <div class="history-strip">
        <button
          v-for="v in shot.versions.filter((v) => v.kind === history)"
          :key="v.id"
          class="history-item"
          :class="{
            active: v.id === shot.imageVersion || v.id === shot.videoVersion,
          }"
          @click.stop="store.useVersion(shot.id, v.id)"
        >
          <MediaThumb :media="v.media" :label="v.label" />
          <div>
            <span>{{ v.label }}</span
            ><Check v-if="v.id === shot.imageVersion || v.id === shot.videoVersion" :size="13" />
          </div>
          <small>{{ v.time }}</small>
        </button>
      </div>
    </div>
  </article>
</template>
