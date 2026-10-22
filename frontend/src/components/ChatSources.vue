<script setup lang="ts">
import { computed } from 'vue';
import type { ChatMessage } from '../types';
import { useStudio } from '../stores/studio';
const props = defineProps<{ activity: ChatMessage['activity'] }>();
const store = useStudio();
const sources = computed(() => [...new Map(props.activity.flatMap(a => a.type === 'search' ? a.sources || [] : []).filter(s => /^https?:\/\//i.test(s.url)).map(s => [s.url, s])).values()]);
const hasError = computed(() => props.activity.some(a => a.type === 'error'));
</script>
<template>
  <div v-if="sources.length || hasError" class="chat-sources">
    <p v-if="hasError" class="chat-source-error">部分辅助资料未能取得，你可以重新尝试。本次操作结果以确认窗口和生成记录为准。</p>
    <template v-if="sources.length"><span>参考来源</span><a v-for="source in sources" :key="source.url" :href="source.url" @click.prevent="store.openLink(source.url)">{{ source.title || '查看来源' }}</a></template>
  </div>
</template>
