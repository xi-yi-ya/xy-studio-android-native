<script setup lang="ts">
import {ref,watch} from 'vue';
import {Image as ImageIcon} from 'lucide-vue-next';
const props=defineProps<{media?:string|null;label?:string}>();
const failed=ref(false);watch(()=>props.media,()=>failed.value=false);
</script>
<template><div class="media-thumb" :aria-label="label"><img v-if="media && !failed" :src="media" :alt="label" loading="lazy" @error="failed=true"/><div v-else class="media-empty"><ImageIcon :size="25" :stroke-width="1.3"/><span>{{failed?'图片读取失败，请检查原文件':label || '等待你的第一个版本'}}</span></div></div></template>
