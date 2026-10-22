<script setup lang="ts">
import { computed } from 'vue';
import {
  MoreHorizontal,
  Pencil,
  Sparkles,
  History,
  Send,
  Trash2,
  Check,
  ImagePlus,
} from 'lucide-vue-next';
import {
  ContextMenuRoot,
  ContextMenuTrigger,
  ContextMenuPortal,
  ContextMenuContent,
  ContextMenuItem,
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuPortal,
  DropdownMenuContent,
  DropdownMenuItem,
} from 'reka-ui';
import type { Asset } from '../types';
import { useStudio } from '../stores/studio';
import MediaThumb from './MediaThumb.vue';
const props = defineProps<{ asset: Asset }>();
const emit = defineEmits<{
  edit: [id: string];
  delete: [id: string];
  choose: [id: string];
  history: [id: string];
  preview: [id: string];
}>();
const store = useStudio();
const current = computed(() => props.asset.versions.find((v) => v.id === props.asset.current));

function selectCard(event: MouseEvent) {
  if (
    (event.target as HTMLElement).closest(
      'button, a, input, select, textarea, summary, [role="menuitem"]',
    )
  )
    return;
  store.toggleSelection(props.asset.id);
}
function preview() {
  store.select(props.asset.id);
  emit('preview', props.asset.id);
}
const items = [
  { action: 'choose', name: '替换图片', icon: ImagePlus },
  { action: 'context', name: '发送给 AI', icon: Send },
  { action: 'edit', name: '修改名称', icon: Pencil },

  { action: 'history', name: '查看历史版本', icon: History },
  { action: 'delete', name: '删除素材', icon: Trash2 },
];
function act(action: string) {
  if (action === 'context') {
    store.pin(props.asset.id);
    store.notify(`已将「${props.asset.name}」发送到 AI 上下文`);
  } else if (action === 'delete') emit('delete', props.asset.id);
  else if (action === 'choose') emit('choose', props.asset.id);
  else emit(action as 'edit', props.asset.id);
}
</script>
<template>
  <ContextMenuRoot
    ><ContextMenuTrigger as-child>
      <article
        class="asset-card surface"
        :class="{ selected: store.selectedId === asset.id }"
        :data-testid="`asset-${asset.id}`"
        @click="selectCard"
      >
        <button
          class="asset-image"
          :aria-label="`查看${asset.name}大图`"
          :aria-pressed="store.selectedId === asset.id"
          @click.stop="store.toggleSelection(asset.id)"
          @dblclick.stop="preview"
        >
          <MediaThumb :media="current?.media" :label="asset.name" /><span
            v-if="store.selectedId === asset.id"
            class="selection-check"
            ><Check :size="13"
          /></span>
        </button>
        <div class="asset-info">
          <div class="flex items-center justify-between gap-2">
            <h3>{{ asset.name }}</h3>
            <DropdownMenuRoot
              ><DropdownMenuTrigger class="icon-btn" :aria-label="`${asset.name}更多操作`"
                ><MoreHorizontal :size="19" /></DropdownMenuTrigger
              ><DropdownMenuPortal
                ><DropdownMenuContent class="menu-content" align="end"
                  ><DropdownMenuItem
                    v-for="item in items"
                    :key="item.action"
                    class="menu-item"
                    :class="{ danger: item.action === 'delete' }"
                    @select="act(item.action)"
                    ><component :is="item.icon" :size="15" />{{ item.name }}</DropdownMenuItem
                  ></DropdownMenuContent
                ></DropdownMenuPortal
              ></DropdownMenuRoot
            >
          </div>
        </div>

        <footer>
          <button @click.stop="emit('choose', asset.id)">
            <ImagePlus :size="15" />{{ current ? '替换图片' : '添加图片' }}</button
          ><button :aria-label="`${asset.name}历史版本`" @click.stop="emit('history', asset.id)">
            <History :size="15" />历史
          </button>
        </footer>
      </article> </ContextMenuTrigger
    ><ContextMenuPortal
      ><ContextMenuContent class="menu-content"
        ><ContextMenuItem
          v-for="item in items"
          :key="item.action"
          class="menu-item"
          :class="{ danger: item.action === 'delete' }"
          @select="act(item.action)"
          ><component :is="item.icon" :size="15" />{{ item.name }}</ContextMenuItem
        ></ContextMenuContent
      ></ContextMenuPortal
    ></ContextMenuRoot
  >
</template>
