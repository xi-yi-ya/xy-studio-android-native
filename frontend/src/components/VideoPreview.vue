<script setup lang="ts">
import {ref,computed,watch} from 'vue';
import {Play,Pause,Maximize2,Volume2,VolumeX} from 'lucide-vue-next';
import MediaThumb from './MediaThumb.vue';
const props=defineProps<{media?:string|null;url?:string|null;duration:number;label:string;file?:string;notice?:string}>();
const emit=defineEmits<{enlarge:[];fallback:[file:string]}>();
const video=ref<HTMLVideoElement>(),playing=ref(false),position=ref(0),length=ref(props.duration),muted=ref(false),failed=ref('');
const clock=(n:number)=>`${String(Math.floor(n/60)).padStart(2,'0')}:${String(Math.floor(n%60)).padStart(2,'0')}`;
const timestamp=computed(()=>clock(position.value));
watch(()=>props.url,()=>{playing.value=false;position.value=0;length.value=props.duration;failed.value=''});
function metadata(event:Event){const element=event.currentTarget as HTMLVideoElement;if(element!==video.value)return;length.value=element.duration}
function timeUpdate(event:Event){const element=event.currentTarget as HTMLVideoElement;if(element!==video.value)return;position.value=element.currentTime}
async function toggle(){try{if(!video.value)return;if(video.value.paused)await video.value.play();else video.value.pause()}catch(e){failed.value=String(e)}}
function seek(event:Event){if(video.value)video.value.currentTime=Number((event.target as HTMLInputElement).value)}
</script>
<template><div class="video-preview"><video v-if="url" ref="video" :src="url" :poster="media || undefined" :muted="muted" preload="metadata" :aria-label="label" @loadedmetadata="metadata" @play="playing=true" @pause="playing=false" @ended="playing=false" @timeupdate="timeUpdate" @error="failed='该媒体解码失败，可以使用系统播放器查看原文件'"/><MediaThumb v-else :media="media" :label="notice || (media?'视频预览':'视频尚未生成')"/><button v-if="url && !playing && !failed" class="big-play" aria-label="播放视频" @click.stop="toggle"><Play :size="24" fill="currentColor"/></button><div v-if="failed" class="video-error"><span>{{failed}}</span><button v-if="file" class="btn" @click.stop="emit('fallback',file)">使用系统播放器</button></div><div v-if="url" class="video-controls" @click.stop><button :aria-label="playing?'暂停视频':'播放视频'" @click="toggle"><Pause v-if="playing" :size="15"/><Play v-else :size="15"/></button><input :value="position" type="range" min="0" :max="Number.isFinite(length)?length:duration" step=".05" aria-label="视频进度" @input="seek"/><span>{{timestamp}} / {{clock(length || duration)}}</span><button aria-label="静音开关" @click="muted=!muted"><VolumeX v-if="muted" :size="14"/><Volume2 v-else :size="14"/></button><button aria-label="放大预览" @click="emit('enlarge')"><Maximize2 :size="14"/></button></div></div></template>
