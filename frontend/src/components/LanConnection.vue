<script setup lang="ts">
import {ref} from 'vue';
import {lan,pair,reconnect,forget} from '../lan';
import {useStudio} from '../stores/studio';
const store=useStudio();
const open=ref(false), address=ref(lan.base || ''), code=ref(''), name=ref('我的 Android');
async function submit(){try{await pair(address.value,code.value,name.value);code.value='';store.connectionError='';open.value=false}catch{}}
async function retry(){try{await reconnect();store.connectionError=''}catch(e){lan.error=String(e)}}
function disconnect(){forget();store.state=null;store.ready=false;open.value=true}
</script>
<template>
  <div class="lan-status"><span :class="{'lan-online':lan.connected}">● {{lan.status}}</span><button class="text-action" @click="open=!open">连接设置</button><button v-if="!lan.connected" class="text-action" @click="retry">重新连接</button></div>
  <section v-if="open || !store.ready" class="lan-connect surface">
    <form @submit.prevent="submit"><h1>连接你的 XY Studio</h1><p>手机与 PC 连接同一局域网。在 PC 启动 LAN 服务并授权项目，填写服务窗口中的地址和配对码。</p>
    <label>PC 服务地址<input v-model="address" placeholder="http://192.168.1.10:8765" required aria-label="PC 服务地址" autocapitalize="none" /></label>
    <label>一次性配对码<input v-model="code" inputmode="numeric" pattern="[0-9]{8}" maxlength="8" required aria-label="一次性配对码" autocomplete="off" /></label>
    <label>设备名称<input v-model="name" maxlength="60" required aria-label="设备名称" /></label>
    <p v-if="lan.error" role="alert">{{lan.error}}</p><button class="btn btn-primary" :disabled="lan.pairing">{{lan.pairing?'连接中…':'配对并连接'}}</button>
    <button v-if="store.ready" type="button" class="btn" @click="disconnect">断开并清除授权</button>
    <p class="form-note">项目、生成素材、模型与 API Key 均保留在 PC。授权在本次手机会话中保留，最长 8 小时；仅在可信 Wi-Fi 使用。</p></form>
  </section>
</template>
