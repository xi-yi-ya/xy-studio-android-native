<script setup lang="ts">
import {computed} from 'vue';
import {useStudio} from '../stores/studio';
const props=defineProps<{text:string}>(),store=useStudio();
const parts=computed(()=>{const result:{text:string;url?:string}[]=[];const regex=/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;let at=0;for(const m of props.text.matchAll(regex)){result.push({text:props.text.slice(at,m.index)});result.push({text:m[1]!,url:m[2]});at=m.index!+m[0].length;}result.push({text:props.text.slice(at)});return result;});
</script>
<template><span v-for="(part,i) in parts" :key="i"><a v-if="part.url" :href="part.url" @click.prevent="store.openLink(part.url)">{{part.text}}</a><template v-else>{{part.text}}</template></span></template>
