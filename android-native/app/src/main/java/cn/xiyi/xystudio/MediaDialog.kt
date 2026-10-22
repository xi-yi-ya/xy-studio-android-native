package cn.xiyi.xystudio

import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.common.PlaybackException
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import org.json.JSONObject
import kotlinx.coroutines.delay

@Composable fun MediaDialog(vm:StudioViewModel,version:JSONObject) {
    Dialog(onDismissRequest={vm.preview=null},properties=DialogProperties(usePlatformDefaultWidth=false)) {
        Surface(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding(),color=Color(0xFF11151D)) {
            Column {
                Row(Modifier.padding(12.dp)) {
                    Text(if(version.optString("kind")=="video")"视频预览" else "图片预览 · 双指缩放",color=Color.White,modifier=Modifier.weight(1f))
                    TextButton(onClick={vm.preview=null}){Text("关闭",color=Color.White)}
                }
                if(version.optString("kind")=="video") {
                    val raw=version.optString("originalUrl").ifEmpty{version.optString("url")}
                    NativeVideo(vm.api.media(raw),Modifier.weight(1f).fillMaxWidth())
                } else {
                    var scale by remember(version) { mutableFloatStateOf(1f) }
                    var x by remember(version) { mutableFloatStateOf(0f) };var y by remember(version) { mutableFloatStateOf(0f) }
                    Box(Modifier.weight(1f).fillMaxWidth().pointerInput(version){detectTransformGestures { _,pan,zoom,_ -> scale=(scale*zoom).coerceIn(1f,6f);x+=pan.x;y+=pan.y }}) {
                        AssetImage(vm,version.optString("url").ifEmpty{version.optString("media")},"项目图片",Modifier.fillMaxSize().graphicsLayer(scaleX=scale,scaleY=scale,translationX=x,translationY=y))
                    }
                    TextButton(onClick={scale=1f;x=0f;y=0f}){Text("适应屏幕",color=Color.White)}
                    if(vm.generation==null && version.optString("file").isNotEmpty())Row(Modifier.padding(horizontal=16.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                        Button(onClick={vm.openGeneration("video",reference=version.getString("file"))},enabled=vm.connected&&!vm.working){Text("用此图制作视频")}
                        TextButton(onClick={vm.openGeneration("image",reference=version.getString("file"))},enabled=vm.connected&&!vm.working){Text("编辑这张图",color=Color.White)}
                    }
                }
                Text(version.optString("prompt"),color=Color.White,maxLines=4,modifier=Modifier.padding(16.dp),style=MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@androidx.annotation.OptIn(androidx.media3.common.util.UnstableApi::class)
@Composable fun NativeVideo(url:String,modifier:Modifier=Modifier) {
    val context=LocalContext.current
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    var error by remember(url) { mutableStateOf("") }
    var playback by remember(url) { mutableStateOf("等待播放") }
    val player=remember(url) {
        ExoPlayer.Builder(context).build().apply {
            addListener(object:Player.Listener { override fun onPlayerError(e:PlaybackException){error="视频无法播放：${e.errorCodeName}。请检查连接或原文件编码。"} })
            if(url.isNotEmpty()){setMediaItem(MediaItem.fromUri(url));prepare()}
        }
    }
    DisposableEffect(player,lifecycle) {
        val observer=LifecycleEventObserver { _,event -> if(event==Lifecycle.Event.ON_STOP)player.pause() }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer);player.release() }
    }
    LaunchedEffect(player) {
        while(true) {
            playback = "已播放 ${player.currentPosition / 1000.0} 秒" + if(player.isPlaying)" · 播放中" else " · 已暂停"
            delay(250)
        }
    }
    Column(modifier.background(Color.Black)) {
        if(url.isEmpty())Text("预览尚未就绪，请关闭并刷新素材。",color=Color.White)
        AndroidView(factory={PlayerView(it).apply{this.player=player;useController=true}},update={it.player=player},modifier=Modifier.weight(1f).fillMaxWidth())
        Row(Modifier.padding(8.dp)) {
            TextButton(onClick={if(player.isPlaying)player.pause() else {if(player.playbackState==Player.STATE_ENDED)player.seekTo(0);player.play()}}){Text("播放 / 暂停",color=Color.White)}
            Text(playback,color=Color.White,modifier=Modifier.padding(8.dp),style=MaterialTheme.typography.labelSmall)
        }
        if(error.isNotEmpty())Text(error,color=Color.White,modifier=Modifier.padding(12.dp))
    }
}
