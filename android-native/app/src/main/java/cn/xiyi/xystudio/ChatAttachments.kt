package cn.xiyi.xystudio

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

@Composable
fun ChatAttachments(vm:StudioViewModel) {
    var choosing by remember { mutableStateOf(false) }
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if(uri!=null)vm.importMedia(uri,kind="auto",attachToChat=true)
    }
    val media=vm.state.rows("mediaContext")
    val ids=(vm.state.strings("contextIds")+listOf(vm.state.optString("selectedId")).filter{it.isNotBlank()&&it!="null"}).distinct()
    val entries=vm.project?.let{it.rows("assets")+it.rows("shots")} ?: emptyList()
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.horizontalScroll(rememberScrollState()),verticalAlignment=Alignment.CenterVertically) {
            TextButton(onClick={choosing=true},enabled=vm.connected&&!vm.working,modifier=Modifier.testTag("chatAddMedia")){Text("＋ 图片 / 视频")}
            TextButton(onClick={picker.launch(arrayOf("image/png","image/jpeg","image/webp","video/mp4","video/webm","video/x-matroska"))},enabled=vm.connected&&!vm.working,modifier=Modifier.testTag("chatImportMedia")){Text("从手机导入")}
            if(media.isNotEmpty()||ids.isNotEmpty())TextButton(onClick={vm.command("context.clear")},enabled=!vm.working,modifier=Modifier.testTag("clearChatContext")){Text("清空引用")}
        }
        if(media.isNotEmpty()||ids.isNotEmpty()) {
            Text("下一条消息引用 ${media.size} 份素材 · ${ids.size} 个条目",Modifier.padding(horizontal=16.dp),style=MaterialTheme.typography.labelSmall)
            LazyRow(contentPadding=PaddingValues(horizontal=12.dp,vertical=6.dp),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                items(media,key={it.getString("file")}) { item ->
                    val file=item.getString("file")
                    StudioCard(Modifier.width(192.dp).testTag("chatAttachment:$file")) {
                        Row(Modifier.padding(8.dp),verticalAlignment=Alignment.CenterVertically) {
                            Box(Modifier.size(48.dp).clickable(enabled=!vm.working){vm.previewFile(file)},contentAlignment=Alignment.Center) {
                                if(item.optString("media").isNotBlank())AssetImage(vm,item.optString("media"),item.optString("name"),Modifier.fillMaxSize())
                                else StudioIcon("video",tint=MaterialTheme.colorScheme.primary)
                            }
                            Column(Modifier.weight(1f).padding(start=8.dp)) {
                                Text(item.optString("name"),maxLines=1,style=MaterialTheme.typography.labelMedium)
                                Text(if(item.optString("kind")=="video")"视频" else "图片",style=MaterialTheme.typography.labelSmall)
                            }
                            TextButton(onClick={vm.command("context.remove",obj("file" to file))},enabled=!vm.working,modifier=Modifier.testTag("removeAttachment:$file").width(48.dp),contentPadding=PaddingValues(0.dp)){Text("移除",style=MaterialTheme.typography.labelSmall)}
                        }
                    }
                }
                items(ids) { id ->
                    InputChip(selected=true,onClick={},label={Text(entries.find{it.optString("id")==id}?.optString("name") ?: "项目条目")},trailingIcon={Text("×",Modifier.clickable(enabled=!vm.working){vm.command("context.remove",obj("id" to id))}.padding(8.dp))})
                }
            }
        }
    }
    if(choosing)ProjectMediaPicker(vm,selected=media.map{it.getString("file")}.toSet(),close={choosing=false}) { item -> vm.command("context.add_media",obj("file" to item.getString("file"))) }
}
