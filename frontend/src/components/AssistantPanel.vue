<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import {
  Sparkles,
  ChevronRight,
  Globe2,
  ArrowUp,
  Paperclip,
  Check,
  X,
  SlidersHorizontal,
  Focus,
  ChevronDown,
} from 'lucide-vue-next';
import MediaThumb from './MediaThumb.vue';
import MessageText from './MessageText.vue';
import ChatSources from './ChatSources.vue';
import { useStudio } from '../stores/studio';
import type { Suggestion } from '../types';
const store = useStudio();
const emit = defineEmits<{ review: [suggestion: Suggestion] }>();
const draft = ref('');
const expanded = ref<string[]>([]);
const messages = ref<HTMLElement>();
const userMessages = computed(() => store.project.chat.filter((m) => m.role === 'user'));
const jump = ref('');
const pins = computed(() =>
  (store.state?.contextIds || []).map((id) => ({
    id,
    name:
      store.project.assets.find((a) => a.id === id)?.name ||
      store.project.shots.find((s) => s.id === id)?.name ||
      '素材',
  })),
);
const hasContext = computed(
  () => !!store.selection || !!pins.value.length || !!store.state?.mediaContext.length,
);
async function bottom() {
  await nextTick();
  if (messages.value) messages.value.scrollTop = messages.value.scrollHeight;
}
async function send() {
  if (!draft.value.trim()) return;
  await store.sendChat(draft.value);
  draft.value = '';
  bottom();
}
watch(() => store.project.chat.length, bottom);
watch(() => store.project.id, bottom);
function jumpTo() {
  document
    .getElementById(`chat-${jump.value}`)
    ?.scrollIntoView({ block: 'center', behavior: 'smooth' });
}
</script>
<template>
  <aside class="assistant-panel" aria-label="AI 助手">
    <header class="assistant-header">
      <div class="flex items-center gap-2.5">
        <span class="assistant-spark"><Sparkles :size="18" /></span>
        <h2>AI 助手</h2>
        <span class="mock-tag">DeepSeek</span>
      </div>
      <button class="icon-btn" aria-label="收起 AI 助手" @click="store.assistantOpen = false">
        <ChevronRight :size="19" />
      </button>
    </header>
    <div class="assistant-options">
      <label class="model-select"
        ><Sparkles :size="13" /><select v-model="store.model" aria-label="AI 模型">
          <option v-for="model in store.state?.config.models" :key="model">
            {{ model }}
          </option></select
        ><ChevronDown :size="12" /></label
      ><label class="online-switch" title="使用同一 DeepSeek Key 联网检索，会产生费用"
        ><Globe2 :size="14" /><span>联网</span
        ><input v-model="store.online" type="checkbox" aria-label="允许联网检索" /><span
          class="mini-switch"
          :class="{ on: store.online }"
      /></label>
    </div>
    <div v-if="store.selection" class="context-banner">
      <Focus :size="14" /><span
        >正在讨论 <strong>{{ store.selection.name }}</strong></span
      ><button
        class="icon-btn"
        :aria-label="`取消讨论${store.selection.name}`"
        @click="store.removeContext(store.selection.id)"
      >
        <X :size="13" />
      </button>
    </div>
    <div v-if="hasContext" class="context-summary">
      <span>用于下一条消息的引用</span
      ><button class="text-action" aria-label="清除 AI 上下文" @click="store.clearContext">
        清空
      </button>
    </div>
    <div v-if="pins.length || store.state?.mediaContext.length" class="context-pins">
      <span v-for="pin in pins" :key="pin.id"
        >{{ pin.name
        }}<button
          class="icon-btn"
          :aria-label="`移除AI引用${pin.name}`"
          @click="store.removeContext(pin.id)"
        >
          <X :size="12" /></button
      ></span>
      <span v-for="media in store.state?.mediaContext" :key="media.file" class="media-attachment"
        ><MediaThumb v-if="media.media" :media="media.media" :label="media.name" />{{
          media.kind === 'video' ? '视频' : '图片'
        }}
        · {{ media.name
        }}<button
          class="icon-btn"
          :aria-label="`移除AI素材引用${media.name}`"
          @click="store.removeMediaContext(media.file)"
        >
          <X :size="12" /></button
      ></span>
    </div>
    <div ref="messages" class="chat-scroll" aria-live="polite">
      <div class="chat-day">今天 · 继续你的创作</div>
      <article
        v-for="message in store.project.chat"
        :key="message.id"
        :id="`chat-${message.id}`"
        class="message"
        :class="message.role"
      >
        <div class="message-meta">
          <span v-if="message.role === 'assistant'" class="bot-avatar"><Sparkles :size="13" /></span
          ><span>{{
            message.role === 'user' ? '你' : message.role === 'tool' ? '操作结果' : 'XY 创作助手'
          }}</span
          ><time>{{ message.time }}</time>
        </div>
        <div class="message-bubble">
          <span v-if="message.targetName" class="message-context"
            >关于 {{ message.targetName }}</span
          >
          <p
            :class="{
              clamped: message.text.length > 320 && !expanded.includes(message.id),
            }"
          >
            <MessageText :text="message.text" />
          </p>
          <button
            v-if="message.text.length > 320"
            class="text-action mt-2"
            @click="
              expanded.includes(message.id)
                ? (expanded = expanded.filter((id) => id !== message.id))
                : expanded.push(message.id)
            "
          >
            {{
              expanded.includes(message.id)
                ? message.role === 'user'
                  ? '收起消息'
                  : '收起长回复'
                : message.role === 'user'
                  ? '展开完整消息'
                  : '展开完整回复'
            }}
          </button>
        </div>
        <ChatSources :activity="message.activity || []" />
      </article>
      <div v-if="store.state?.review" class="suggestion-card">
        <div class="suggestion-title">
          <SlidersHorizontal :size="14" /><strong>{{ store.state.review.title }}</strong
          ><span>待审阅</span>
        </div>
        <p>
          {{
            store.state.review.targetName ||
            store.state.review.args.name ||
            store.state.review.args.description ||
            store.state.review.args.text
          }}
        </p>
        <div class="suggestion-actions">
          <button class="btn btn-primary" @click="emit('review', store.state.review!)">
            审阅操作</button
          ><button class="btn" @click="store.reviewSuggestion(store.state.review!, false)">
            拒绝
          </button>
        </div>
      </div>
      <div v-if="store.busy" class="thinking">
        <Sparkles :size="14" /><span>{{ store.state?.status }}</span>
      </div>
    </div>
    <div class="chat-jump">
      <select v-model="jump" aria-label="定位我的消息" @change="jumpTo">
        <option value="">定位我的消息…</option>
        <option v-for="(m, i) in userMessages" :key="m.id" :value="m.id">
          {{ i + 1 }}. {{ m.text.slice(0, 25) }}
        </option></select
      ><button aria-label="跳到最新消息" @click="bottom">
        <ChevronDown :size="15" />
      </button>
    </div>
    <button class="text-action import-agent" @click="store.importAgent">导入 AI 操作建议</button
    ><button
      class="text-action import-agent"
      :disabled="store.state?.modelsBusy"
      @click="store.refreshModels"
    >
      刷新账户模型
    </button>
    <form class="chat-composer" @submit.prevent="send">
      <textarea
        v-model="draft"
        aria-label="给 AI 助手的消息"
        placeholder="描述你的创作想法；可从素材库发送图片作为参考…"
        rows="3"
        @keydown.ctrl.enter.prevent="send"
      />
      <footer>
        <button
          type="button"
          class="icon-btn"
          aria-label="引用当前素材"
          @click="
            store.selection ? store.pin(store.selection.id) : store.notify('先选中一个素材或镜头')
          "
        >
          <Paperclip :size="17" /></button
        ><span>Ctrl + Enter 发送</span
        ><button
          class="send-btn"
          aria-label="发送消息"
          :disabled="!draft.trim() || store.busy || !store.hasProject"
        >
          <ArrowUp :size="20" />
        </button>
      </footer>
    </form>
    <p class="assistant-footnote">
      {{ store.state?.status || '描述你的创作想法 · 操作前由你确认' }}
    </p>
  </aside>
</template>
