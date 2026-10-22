package cn.xiyi.xystudio

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.CancellationException
import org.json.JSONObject

/** Project-scoped picker, independent of the main library's filters and scroll position. */
@Composable
fun ProjectMediaPicker(vm:StudioViewModel, title:String="选择参考素材", initialKind:String="image",
    allowVideo:Boolean=true, selected:Set<String> = emptySet(), close:()->Unit, choose:(JSONObject)->Unit) {
    var kind by remember { mutableStateOf(initialKind) }
    var draft by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    var offset by remember { mutableIntStateOf(0) }
    var retry by remember { mutableIntStateOf(0) }
    var records by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var total by remember { mutableIntStateOf(0) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf("") }
    val projectId=remember { vm.project?.optString("id") }
    LaunchedEffect(vm.project?.optString("id")) { if(vm.project?.optString("id")!=projectId)close() }
    LaunchedEffect(kind,query,offset,retry) {
        loading=true;error="";records=emptyList()
        try {
            val result=vm.call("library.query",obj("kind" to kind,"query" to query,"offset" to offset,"limit" to 40)) as JSONObject
            records=result.rows("items");total=result.optInt("total")
        } catch(e:CancellationException){throw e} catch(e:Exception){error=e.message ?: "无法加载素材，请重试"}
        finally { loading=false }
    }
    Dialog(onDismissRequest=close,properties=DialogProperties(usePlatformDefaultWidth=false)) {
        Surface(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding(),color=MaterialTheme.colorScheme.background) {
            Column(Modifier.imePadding().padding(horizontal=16.dp)) {
                Row(verticalAlignment=Alignment.CenterVertically) {
                    Text(title,Modifier.weight(1f),style=MaterialTheme.typography.titleLarge)
                    TextButton(onClick=close,modifier=Modifier.testTag("closeMediaPicker")){Text("完成")}
                }
                Row(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    FilterChip(kind=="image",{kind="image";offset=0},label={Text("图片")},modifier=Modifier.testTag("pickKind:image"))
                    if(allowVideo)FilterChip(kind=="video",{kind="video";offset=0},label={Text("视频")},modifier=Modifier.testTag("pickKind:video"))
                }
                Row(verticalAlignment=Alignment.CenterVertically) {
                    OutlinedTextField(draft,{draft=it},label={Text("搜索项目素材")},singleLine=true,modifier=Modifier.weight(1f))
                    TextButton(onClick={query=draft;offset=0;retry++}){Text("搜索")}
                }
                Text(if(title=="选择参考素材")"点选加入下一条消息的参考；已添加的素材会标记。" else "选择真实项目素材，原有版本会保留。",style=MaterialTheme.typography.bodySmall,modifier=Modifier.padding(vertical=8.dp))
                if(loading)LinearProgressIndicator(Modifier.fillMaxWidth())
                if(error.isNotEmpty()) { Text(error,color=MaterialTheme.colorScheme.error);TextButton(onClick={retry++}){Text("重试") } }
                if(!loading&&error.isEmpty()&&records.isEmpty())Text("没有找到素材，可从手机导入后再选择。",Modifier.padding(vertical=20.dp))
                LazyColumn(Modifier.weight(1f),verticalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(vertical=8.dp)) {
                    items(records,key={it.getString("file")}) { media ->
                        val file=media.getString("file");val attached=file in selected
                        StudioCard(Modifier.fillMaxWidth().testTag("pickMedia:$file").clickable(enabled=vm.connected&&!vm.working&&!attached){choose(media)}) {
                            Row(Modifier.padding(10.dp),verticalAlignment=Alignment.CenterVertically) {
                                AssetImage(vm,media.optString("media"),media.optString("name"),Modifier.size(76.dp))
                                Column(Modifier.weight(1f).padding(start=12.dp)) {
                                    Text(media.optString("name"),maxLines=2,style=MaterialTheme.typography.titleMedium)
                                    Text(if(kind=="video")"视频" else "图片",style=MaterialTheme.typography.labelSmall)
                                    Text(if(attached)"已添加" else "选择",color=MaterialTheme.colorScheme.primary)
                                }
                            }
                        }
                    }
                }
                Row(verticalAlignment=Alignment.CenterVertically) {
                    Text("共 $total 份素材",Modifier.weight(1f),style=MaterialTheme.typography.labelSmall)
                    TextButton(onClick={offset=(offset-40).coerceAtLeast(0)},enabled=offset>0&&!loading){Text("上页")}
                    TextButton(onClick={offset+=40},enabled=offset+40<total&&!loading){Text("下页")}
                }
                if(vm.working)LinearProgressIndicator(Modifier.fillMaxWidth())
                if(vm.error.isNotBlank())Text(vm.error,color=MaterialTheme.colorScheme.error,style=MaterialTheme.typography.bodySmall)
            }
        }
    }
}
