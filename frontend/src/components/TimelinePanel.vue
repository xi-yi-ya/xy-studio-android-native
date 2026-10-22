<script setup lang="ts">
import { Play, Clapperboard, ChevronRight } from "lucide-vue-next";
import MediaThumb from "./MediaThumb.vue";
import { useStudio } from "../stores/studio";
const store = useStudio();
const emit = defineEmits<{ locate: [id: string] }>();
</script>
<template>
  <section class="timeline-panel" aria-label="镜头时间轴">
    <header>
      <div class="flex items-center gap-2">
        <Clapperboard :size="14" />
        <h2>镜头时间轴</h2>
        <span>{{ store.project.shots.length }} 个镜头</span>
      </div>
      <span
        >总时长 <strong>{{ store.totalDuration }} 秒</strong>
        <ChevronRight :size="12"
      /></span>
    </header>
    <div class="timeline-track">
      <button
        v-for="(shot, i) in store.project.shots"
        :key="shot.id"
        class="timeline-item"
        :class="{ active: store.selectedId === shot.id }"
        :aria-label="`定位镜头${i + 1} ${shot.name}`"
        :aria-pressed="store.selectedId === shot.id"
        @click="emit('locate', shot.id)"
      >
        <MediaThumb
          :media="shot.versions.find((v) => v.id === shot.imageVersion)?.media"
          :label="shot.imageVersion ? shot.name : '待制作'"
        />
        <div>
          <span class="timeline-number">{{
            String(i + 1).padStart(2, "0")
          }}</span
          ><strong>{{ shot.name }}</strong
          ><small>{{ shot.duration ? Number(shot.duration.toFixed(2))+'s' : '待定' }}</small>
        </div>
        <span class="timeline-indicator" />
      </button>
      <div v-if="!store.project.shots.length" class="timeline-empty">
        添加一个镜头，故事就从这里开始。
      </div>
    </div>
    <div class="timeline-ruler">
      <span>顺序预览</span><span>点击镜头定位 · 版本保留在原卡片</span
      ><span>{{ store.totalDuration }}s</span>
    </div>
  </section>
</template>
