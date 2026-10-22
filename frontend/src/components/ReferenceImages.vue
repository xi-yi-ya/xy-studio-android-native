<script setup lang="ts">
import { ref, watch } from 'vue';
import { ArrowUp, ArrowDown, X } from 'lucide-vue-next';
import { useStudio } from '../stores/studio';
import MediaThumb from './MediaThumb.vue';
import StudioDialog from './StudioDialog.vue';
const props = defineProps<{ files: string[]; editable?: boolean }>();
const emit = defineEmits<{ move: [index: number, delta: number]; remove: [index: number] }>();
const store = useStudio();
const rows = ref<
    { file: string; name: string; media: string; exists: boolean; trashed?: boolean }[]
  >([]),
  large = ref<{ name: string; media: string } | null>(null);
let serial = 0;
watch(
  () => [...props.files, store.project.id],
  async () => {
    const version = ++serial;
    if (!props.files.length) {
      rows.value = [];
      return;
    }
    try {
      const value = await store.api<typeof rows.value>('references.describe', {
        files: props.files,
      });
      if (version === serial) rows.value = value;
    } catch {
      if (version === serial) rows.value = [];
    }
  },
  { immediate: true },
);
</script>
<template>
  <div class="reference-images">
    <div v-for="(row, i) in rows" :key="`${i}-${row.file}`" class="reference-image-row">
      <button
        type="button"
        class="reference-thumb"
        :aria-label="`放大参考图${i + 1}`"
        :disabled="!row.exists"
        @click="large = row"
      >
        <MediaThumb :media="row.media" :label="row.name" />
      </button>
      <div class="reference-image-name">
        <strong>{{ i + 1 }}. {{ row.name }}</strong
        ><small>{{
          row.exists
            ? `参考图 ${i + 1}`
            : row.trashed
              ? '参考图已在回收站，请先恢复'
              : '原文件缺失，请重新选择'
        }}</small>
      </div>
      <template v-if="editable"
        ><button
          type="button"
          class="icon-btn"
          aria-label="上移参考图"
          :disabled="i === 0"
          @click="emit('move', i, -1)"
        >
          <ArrowUp :size="14" /></button
        ><button
          type="button"
          class="icon-btn"
          aria-label="下移参考图"
          :disabled="i === rows.length - 1"
          @click="emit('move', i, 1)"
        >
          <ArrowDown :size="14" /></button
        ><button type="button" class="icon-btn" aria-label="移除参考图" @click="emit('remove', i)">
          <X :size="14" /></button
      ></template>
    </div>
  </div>
  <StudioDialog
    :open="!!large"
    @update:open="(v) => !v && (large = null)"
    :title="large?.name || '参考图预览'"
    wide
    ><MediaThumb class="reference-large" :media="large?.media" label="参考图大图"
  /></StudioDialog>
</template>
