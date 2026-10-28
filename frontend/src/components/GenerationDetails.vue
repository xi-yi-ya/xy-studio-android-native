<script setup lang="ts">
import { computed } from 'vue';
import type { Generation } from '../types';
import { isVideoMode } from '../types';
import { useStudio } from '../stores/studio';
const props = defineProps<{ generation?: Generation; materials?: unknown[] }>();
const store = useStudio();
const cloud = computed(() => props.generation?.mode.startsWith('pixstag_'));
const materialNames = computed(() => (props.materials || []).flatMap(m => typeof m === 'object' && m && 'name' in m ? [String(m.name)] : []));
</script>
<template>
  <div class="generation-details">
    <dl v-if="generation">
      <div><dt>生成方式</dt><dd>{{ store.state?.catalog.modes[generation.mode] || '原生成方式' }}</dd></div>
      <div v-if="cloud"><dt>云端模型</dt><dd>{{generation.api_model}}</dd></div>
      <div v-if="generation.mode !== 'upscale'"><dt>画面设置</dt><dd>{{ cloud ? `${generation.ratio} · ${generation.api_resolution}` : generation.mode==='qwen_edit' && generation.edit_follow_source!==false?'沿用主参考图尺寸':`${generation.ratio} · ${generation.megapixels} MP`}}</dd></div>
      <div v-if="isVideoMode(generation.mode)"><dt>设置时长</dt><dd>{{ generation.seconds }} 秒</dd></div>
      <div v-if="generation.mode === 'upscale'"><dt>放大倍数</dt><dd>{{ generation.scale }}×</dd></div>
      <div v-if="!cloud"><dt>采样步数</dt><dd>{{ generation.steps || '沿用默认设置' }}</dd></div>
      <div v-if="!cloud"><dt>随机种子</dt><dd>{{ generation.seed }}</dd></div>
      <div><dt>参考图片</dt><dd>{{ generation.references.length }} 张</dd></div>
      <div v-if="cloud"><dt>参考视频</dt><dd>{{generation.video_references?.length || 0}} 个</dd></div>
      <div v-if="cloud"><dt>云端选项</dt><dd>提示词优化 {{generation.api_context_ir ? '开' : '关'}} · 水印 {{generation.api_watermark ? '开' : '关'}} · 请求尾帧 {{generation.api_last_frame ? '开' : '关'}}</dd></div>
      <div v-if="generation.mode.startsWith('h3')"><dt>电影质感</dt><dd>{{ generation.cinema ? `已启用 · 强度 ${generation.cinema_strength}` : '未启用' }}</dd></div>
      <div v-if="generation.mode === 'quad'"><dt>四视图效果</dt><dd>{{ generation.quad_lora ? '已启用' : '未启用' }}</dd></div>
      <div v-if="generation.mode === 'krea'"><dt>风格</dt><dd>{{ generation.styles.join('、') || '默认风格' }}</dd></div>
      <div v-if="generation.mode.startsWith('qwen')"><dt>图片模型</dt><dd>{{ generation.qwen_int8 ? '节省显存版本' : '标准版本' }}</dd></div>
    </dl>
    <p v-else class="muted">这张图片没有生成参数记录。</p>
    <p v-if="materialNames.length">使用素材：{{ materialNames.join('、') }}</p>
  </div>
</template>
