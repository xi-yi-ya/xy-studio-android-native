<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { ArrowUp, ArrowDown, Plus, X, RefreshCw } from 'lucide-vue-next';
import { useStudio } from '../stores/studio';
import type { Generation } from '../types';
import MediaLibrary from './MediaLibrary.vue';
import ReferenceImages from './ReferenceImages.vue';
const props = defineProps<{ modelValue: Generation; targetId: string }>();
const emit = defineEmits<{ 'update:modelValue': [g: Generation] }>();
const store = useStudio(),
  summary = ref(''),
  available = ref('');
const modeDrafts = new Map<string, Generation>();
const choosing = ref(false);
function chooseReference(file: string) {
  if (!/\.(png|jpe?g|webp)$/i.test(file)) {
    store.notify('请选择图片作为参考');
    return;
  }
  if (!props.modelValue.references.includes(file)) props.modelValue.references.push(file);
  choosing.value = false;
}
const video = computed(() => props.modelValue.mode.startsWith('h3'));
const modes = computed(() =>
  Object.entries(store.state?.catalog.modes || {}).filter(
    ([mode]) => mode.startsWith('h3') === video.value,
  ),
);
const images = computed(() =>
  [...store.project.assets, ...store.project.shots].filter((a) => a.imageFile),
);
async function modeChanged(mode: string, old: string) {
  const current = JSON.parse(JSON.stringify(props.modelValue)) as Generation;
  modeDrafts.set(old, { ...current, mode: old });
  const saved = await store.defaults(props.targetId, mode);
  if (props.modelValue.mode !== mode) return;
  const draft = modeDrafts.get(mode);
  const value = JSON.parse(JSON.stringify(draft || saved)) as Generation;
  value.mode = mode;
  if (['qwen', 'krea', 'h3_t2v'].includes(mode)) value.references = [];
  else if (!draft && !value.references.length) value.references = [...current.references];
  emit('update:modelValue', value);
}
watch(() => props.modelValue.mode, modeChanged);
let revision = 0;
watch(
  () => props.modelValue,
  async (g) => {
    const serial = ++revision;
    try {
      const s = await store.api<{
        width: number;
        height: number;
        frames: number;
        seconds: number;
        steps: number;
      }>('generation.preview', { generation: g });
      if (serial !== revision) return;
      summary.value =
        `输出 ${s.width} × ${s.height}` +
        (video.value ? ` · ${s.frames} 帧 / 24fps ≈ ${s.seconds.toFixed(2)} 秒` : '') +
        ` · ${s.steps} 步`;
    } catch (e) {
      summary.value = String(e);
    }
  },
  { deep: true, immediate: true },
);
function referenceName(file: string, i: number) {
  return images.value.find((item) => item.imageFile === file)?.name || `参考图片 ${i + 1}`;
}
function add() {
  if (available.value) props.modelValue.references.push(available.value);
}
function move(i: number, n: number) {
  const r = props.modelValue.references;
  const j = i + n;
  if (j < 0 || j >= r.length) return;
  const value = r.splice(i, 1)[0]!;
  r.splice(j, 0, value);
}
async function changeSeed() {
  props.modelValue.seed = await store.api<string>('generation.seed');
}
async function importRefs() {
  const result = await store.api<string[]>('references.import');
  props.modelValue.references.push(...result);
}
</script>
<template>
  <div class="form-content">
    <label
      >工作流<select v-model="modelValue.mode" aria-label="生成工作流">
        <option v-for="[mode, name] in modes" :key="mode" :value="mode">{{ name }}</option>
      </select></label
    ><label v-if="modelValue.mode !== 'upscale'"
      >提示词<textarea
        v-model="modelValue.prompt"
        rows="5"
        required
        aria-label="生成提示词"
      /></label
    ><label v-if="modelValue.mode === 'qwen_edit'"
      >编辑输出尺寸<select
        :value="modelValue.edit_follow_source === false ? 'custom' : 'source'"
        aria-label="编辑输出尺寸"
        @change="
          modelValue.edit_follow_source = ($event.target as HTMLSelectElement).value === 'source'
        "
      >
        <option value="source">沿用主参考图尺寸（推荐）</option>
        <option value="custom">自定义画面比例和分辨率</option>
      </select></label
    >
    <div
      v-if="
        modelValue.mode !== 'upscale' &&
        !(modelValue.mode === 'qwen_edit' && modelValue.edit_follow_source !== false)
      "
      class="form-row"
    >
      <label
        >画面比例<select v-model="modelValue.ratio">
          <option v-for="ratio in store.state?.catalog.ratios" :key="ratio">{{ ratio }}</option>
        </select></label
      ><label
        >分辨率（MP）<input
          v-model.number="modelValue.megapixels"
          type="number"
          min=".1"
          max="16"
          step=".1"
          aria-label="分辨率 MP"
          required
      /></label>
    </div>
    <div class="form-row">
      <label
        >随机种子
        <div class="flex gap-2">
          <input
            v-model="modelValue.seed"
            class="min-w-0 flex-1"
            inputmode="numeric"
            pattern="[0-9]+"
            required
            aria-label="种子"
          /><button
            type="button"
            class="btn"
            aria-label="换一个随机种子"
            title="为本次生成换一个种子"
            @click="changeSeed"
          >
            <RefreshCw :size="14" />
          </button></div></label
      ><label
        >采样步数 · 0 使用默认值<input
          v-model.number="modelValue.steps"
          type="number"
          min="0"
          max="100"
          aria-label="采样步数"
          required
      /></label>
    </div>
    <label v-if="video"
      >H3 时长（秒）<input
        v-model.number="modelValue.seconds"
        type="number"
        min=".2"
        max="149"
        step=".1"
        aria-label="H3 时长"
        required /></label
    ><label v-if="video" class="checkbox-label"
      ><input v-model="modelValue.cinema" type="checkbox" />启用电影质感 LoRA</label
    ><label v-if="video && modelValue.cinema"
      >电影 LoRA 强度<input
        v-model.number="modelValue.cinema_strength"
        type="number"
        min="0"
        max="2"
        step=".1" /></label
    ><label v-if="modelValue.mode === 'quad'" class="checkbox-label"
      ><input v-model="modelValue.quad_lora" type="checkbox" />启用角色四视图 LoRA</label
    ><label v-if="modelValue.mode.startsWith('qwen')" class="checkbox-label"
      ><input v-model="modelValue.qwen_int8" type="checkbox" />使用本机 INT8 模型</label
    >
    <fieldset v-if="modelValue.mode === 'krea'" class="lora-grid">
      <legend>Krea2 风格 LoRA · 分别启停</legend>
      <label
        v-for="(trigger, name) in store.state?.catalog.styles"
        :key="name"
        class="checkbox-label"
        :title="trigger"
        ><input v-model="modelValue.styles" type="checkbox" :value="name" />{{ name }}</label
      >
    </fieldset>
    <label v-if="modelValue.mode === 'upscale'"
      >高清放大倍数 · {{ modelValue.scale }}×<input
        v-model.number="modelValue.scale"
        type="number"
        min="1"
        max="8"
        step=".1"
        aria-label="放大倍数"
        required
    /></label>
    <section v-if="!['qwen', 'krea', 'h3_t2v'].includes(modelValue.mode)" class="reference-picker">
      <h3>参考图 · 按顺序引用</h3>
      <ReferenceImages
        :files="modelValue.references"
        editable
        @move="move"
        @remove="(i) => modelValue.references.splice(i, 1)"
      />
      <p v-if="!modelValue.references.length" class="reference-empty">
        请选择或导入参考图片。图生视频需要一张首帧图。
      </p>
      <div class="form-row">
        <select v-model="available" aria-label="选择项目参考图">
          <option value="">选择项目素材…</option>
          <option v-for="item in images" :key="item.id" :value="item.imageFile">
            {{ item.name }}
          </option></select
        ><button type="button" class="btn" @click="add"><Plus :size="14" />加入参考</button>
      </div>
      <div class="flex gap-2">
        <button type="button" class="btn" @click="importRefs">导入参考图片</button
        ><button type="button" class="btn" @click="choosing = !choosing">
          {{ choosing ? '收起图片库' : '从图片库选择' }}
        </button>
      </div>
      <MediaLibrary
        v-if="choosing"
        kind="image"
        choose-only
        @choose="chooseReference"
        @generate="
          modelValue.mode = 'qwen';
          choosing = false;
        "
      />
    </section>
    <p class="form-note">
      {{ summary }}<br v-if="video" /><span v-if="video"
        >修改时长后请核对提示词时间线；高规格请在本机实测显存。</span
      ><span v-if="modelValue.mode === 'qwen_edit'">
        · 参考图不做居中裁剪。{{
          modelValue.edit_follow_source !== false
            ? '输出沿用第一张参考图尺寸，按 32 像素对齐。'
            : '使用自定义输出画布，请检查构图与参考是否匹配。'
        }}</span
      >
    </p>
  </div>
</template>
