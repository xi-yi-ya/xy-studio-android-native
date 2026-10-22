package cn.xiyi.xystudio

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import kotlinx.coroutines.launch
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import org.json.JSONObject

class MainActivity:ComponentActivity() {
    override fun onCreate(savedInstanceState:Bundle?) {
        super.onCreate(savedInstanceState);enableEdgeToEdge()
        setContent {
            StudioTheme {
                StudioApp(viewModel())
            }
        }
    }
}

@Composable fun ConnectionScreen(vm:StudioViewModel,onConnected:()->Unit) {
    val focus=LocalFocusManager.current
    val keyboard=LocalSoftwareKeyboardController.current
    var code by rememberSaveable { mutableStateOf("") }
    var name by rememberSaveable { mutableStateOf("我的 Android") }
    var awaitingConnection by remember { mutableStateOf(!vm.connected) }
    LaunchedEffect(vm.connected,awaitingConnection){if(vm.connected&&awaitingConnection)onConnected()}
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
        Text("连接你的创作工作台",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold)
        Text("手机与 PC 使用同一局域网。首次填写 PC 服务地址和固定连接密码，之后自动连接。")
        OutlinedTextField(value=vm.address,onValueChange={vm.address=it},label={Text("PC 服务地址")},placeholder={Text("http://192.168.50.198:8765")},singleLine=true,modifier=Modifier.fillMaxWidth())
        OutlinedTextField(value=code,onValueChange={code=it.filter(Char::isDigit).take(12)},label={Text("连接密码（仅首次输入）")},keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.NumberPassword),visualTransformation=androidx.compose.ui.text.input.PasswordVisualTransformation(),singleLine=true,modifier=Modifier.fillMaxWidth())
        OutlinedTextField(value=name,onValueChange={name=it.take(60)},label={Text("设备名称")},singleLine=true,modifier=Modifier.fillMaxWidth())
        Button(onClick={focus.clearFocus();keyboard?.hide();vm.pair(code,name);awaitingConnection=true;code=""},enabled=code.length==12&&!vm.working,modifier=Modifier.fillMaxWidth()){Text("连接并记住设备")}
        if(vm.hasAuthorization||vm.remembered) {
            OutlinedButton(onClick={vm.reconnect();awaitingConnection=true},enabled=!vm.working,modifier=Modifier.fillMaxWidth()){Text("重新连接")}
            TextButton(onClick={vm.disconnect()}){Text("断开并清除授权")}
        }
        Text("连接一次，下次自动回到创作空间。模型、项目和密钥保留在电脑上；在电脑端可更换连接密码。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.secondary)
    }
}

@Composable fun EmptyProject(vm:StudioViewModel):Boolean {
    if(vm.project!=null)return false
    Column(Modifier.padding(24.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Text("先打开一个项目",style=MaterialTheme.typography.titleLarge)
        Text("在 PC 窗口授权已有项目，然后在手机项目列表中选择。")
        Button(onClick={vm.navigate("项目")}){Text("查看项目")}
    }
    return true
}
@Composable fun ProjectsScreen(vm:StudioViewModel) {
    var title by remember { mutableStateOf("") }
    LazyColumn(Modifier.fillMaxSize(),contentPadding=PaddingValues(start=20.dp,end=20.dp,top=8.dp,bottom=96.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item { Text("你的创作空间",style=MaterialTheme.typography.headlineSmall,fontWeight=FontWeight.Bold) }
        item { Row { TextButton(onClick={vm.command("project.save")},enabled=vm.project!=null&&!vm.working){Text("保存当前项目")};TextButton(onClick={vm.refresh()},enabled=!vm.working){Text("刷新项目")} } }
        items(vm.state.rows("recent"),key={it.getString("path")}) { p ->
            StudioCard(Modifier.fillMaxWidth().clickable(enabled=!vm.working&&vm.connected){vm.command("project.open",obj("path" to p.getString("path")))}) {
                Column(Modifier.padding(18.dp),verticalArrangement=Arrangement.spacedBy(6.dp)) {
                    Text(p.optString("title"),style=MaterialTheme.typography.titleMedium)
                    Text("打开 PC 项目 →",color=MaterialTheme.colorScheme.primary)
                }
            }
        }
        item { OutlinedTextField(title,{title=it.take(100)},label={Text("新项目名称")},modifier=Modifier.fillMaxWidth()) }
        item { Button(onClick={vm.command("project.new",obj("title" to title));title=""},enabled=title.isNotBlank()&&!vm.working&&vm.connected){Text("在 PC 新建项目") } }
        item { Text("新项目保存在 PC 服务指定的项目目录；不会覆盖任何已有项目。",style=MaterialTheme.typography.bodySmall) }
    }
}

@Composable fun AssetsScreen(vm:StudioViewModel,kind:String) {
    if(EmptyProject(vm))return
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    val rows=vm.project!!.rows("assets").filter{it.optString("kind")==kind}
    LazyColumn(contentPadding=PaddingValues(start=20.dp,end=20.dp,top=8.dp,bottom=96.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item { Text(if(kind=="characters")"角色资产" else "场景资产",style=MaterialTheme.typography.headlineSmall) }
        item { NewAssetButton(vm,kind) }
        if(rows.isEmpty())item { StudioCard(Modifier.fillMaxWidth()) { Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) { Text(if(kind=="characters")"为故事建立第一个角色" else "为故事找到发生的地方",style=MaterialTheme.typography.titleMedium);Text("先生成一张图片，或从素材库选用已有作品。",style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant);TextButton(onClick={vm.navigate("素材")}){Text("前往素材库")}} } }
        items(rows,key={it.getString("id")}) { asset ->
            StudioCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                    val current=asset.rows("versions").firstOrNull{it.optString("id")==asset.optString("current")}
                    if(current!=null)AssetImage(vm,current.optString("media"),asset.optString("name"),Modifier.fillMaxWidth().height(210.dp).clickable{vm.preview=current})
                    Text(asset.optString("name"),style=MaterialTheme.typography.titleMedium)
                    Text(asset.optString("description"),style=MaterialTheme.typography.bodySmall)
                    Row {
                        TextButton(onClick={editing=asset}){Text("编辑")}
                        TextButton(onClick={vm.command("selection",obj("id" to asset.getString("id"),"pin" to true));vm.navigate("AI")}){Text("发送给 AI")}
                    }
                    WorkspaceActions(vm,asset)
                    VersionHistory(vm,asset)
                }
            }
        }
    }
    editing?.let { EditAssetDialog(vm,it){editing=null} }
}

@Composable fun ShotsScreen(vm:StudioViewModel) {
    if(EmptyProject(vm))return
    var editing by remember { mutableStateOf<JSONObject?>(null) }
    val p=vm.project!!
    val shotScroll=rememberLazyListState()
    val shotScope=rememberCoroutineScope()
    var story by remember(p.optString("id")) { mutableStateOf(p.optString("story")) }
    var storyRevision by remember(p.optString("id")) { mutableIntStateOf(vm.revision) }
    var dirty by remember(p.optString("id")) { mutableStateOf(false) }
    LaunchedEffect(p.optString("story"),vm.revision){if(!dirty){story=p.optString("story");storyRevision=vm.revision}}
    LazyColumn(state=shotScroll,contentPadding=PaddingValues(start=20.dp,end=20.dp,top=8.dp,bottom=96.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item { Text("分镜工作区",style=MaterialTheme.typography.headlineSmall) }
        item { OutlinedTextField(story,{story=it;dirty=true},label={Text("故事")},modifier=Modifier.fillMaxWidth(),minLines=3,maxLines=8) }
        item { Row {
            TextButton(onClick={vm.action{vm.call("project.story",obj("text" to story),storyRevision);dirty=false}},enabled=!vm.working&&vm.connected){Text("保存故事")}
            TextButton(onClick={story=p.optString("story");dirty=false;storyRevision=vm.revision}){Text("重新读取")}
            TextButton(onClick={vm.command("asset.add",obj("kind" to "shots"))},enabled=!vm.working&&vm.connected){Text("添加分镜")}
        } }
        item {
            Text("镜头时间轴 · ${p.rows("shots").size} 个镜头 · ${"%.2f".format(p.rows("shots").sumOf{it.optDouble("duration",0.0)})} 秒",style=MaterialTheme.typography.labelMedium)
            Row(Modifier.horizontalScroll(rememberScrollState()),horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                p.rows("shots").forEachIndexed { index,shot -> AssistChip(onClick={shotScope.launch{shotScroll.animateScrollToItem(4+index)}},label={Text(shot.optString("numberName"))}) }
            }
        }
        items(p.rows("shots"),key={it.getString("id")}) { shot ->
            StudioCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                    Text("${shot.optString("numberName")} · ${shot.optString("name")}",style=MaterialTheme.typography.titleMedium)
                    Text(shot.optString("description"))
                    shot.rows("versions").filter{it.optString("file") in listOf(shot.optString("imageFile"),shot.optString("videoFile"))}.forEach { v ->
                        Box(Modifier.clickable{vm.preview=v}) { AssetImage(vm,v.optString("media"),v.optString("kind"),Modifier.fillMaxWidth().height(190.dp)) }
                    }
                    Text(shot.optString("durationLabel"),style=MaterialTheme.typography.labelMedium)
                    Row {
                        TextButton(onClick={editing=shot}){Text("编辑分镜")}
                        TextButton(onClick={vm.command("selection",obj("id" to shot.getString("id"),"pin" to true));vm.navigate("AI")}){Text("发送给 AI")}
                    }
                    WorkspaceActions(vm,shot,shot=true)
                    VersionHistory(vm,shot)
                }
            }
        }
    }
    editing?.let { EditAssetDialog(vm,it){editing=null} }
}

@Composable fun EditAssetDialog(vm:StudioViewModel,item:JSONObject,close:()->Unit) {
    var name by remember { mutableStateOf(item.optString("name")) }
    var description by remember { mutableStateOf(item.optString("description")) }
    val revision=remember{vm.revision}
    AlertDialog(onDismissRequest=close,title={Text("编辑条目")},text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(name,{name=it},label={Text("名称")})
        OutlinedTextField(description,{description=it},label={Text("描述")},minLines=3,maxLines=8)
    }},confirmButton={TextButton(onClick={vm.action{vm.call("asset.update",obj("id" to item.getString("id"),"name" to name,"description" to description),revision);close()}},enabled=!vm.working){Text("保存到 PC")}},dismissButton={TextButton(onClick=close){Text("取消")}})
}

@Composable fun VersionHistory(vm:StudioViewModel,item:JSONObject) {
    var expanded by remember { mutableStateOf(false) }
    TextButton(onClick={expanded=!expanded}){Text("历史版本 (${item.rows("versions").size})")}
    if(expanded)item.rows("versions").forEach { version ->
        Row(verticalAlignment=Alignment.CenterVertically) {
            TextButton(onClick={vm.preview=version},modifier=Modifier.weight(1f)){Text(version.optString("time").take(19).ifEmpty{"查看历史素材"})}
            TextButton(onClick={vm.command("version.use",obj("id" to item.getString("id"),"version" to version.getString("id")))},enabled=!vm.working){Text("设为当前")}
        }
    }
}

@Composable fun AssetImage(vm:StudioViewModel,url:String,label:String,modifier:Modifier=Modifier) {
    if(url.isNotEmpty())AsyncImage(model=vm.api.media(url),contentDescription=label,contentScale=ContentScale.Fit,modifier=modifier.background(Color(0xFFF0F1F5),RoundedCornerShape(8.dp)))
    else Box(modifier.background(Color(0xFFF0F1F5)),contentAlignment=Alignment.Center){Text("暂无预览",style=MaterialTheme.typography.bodySmall)}
}

@Composable fun LibraryScreen(vm:StudioViewModel) {
    if(EmptyProject(vm))return
    val picker=rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()){uri->if(uri!=null)vm.importMedia(uri)}
    var adopt by remember { mutableStateOf<JSONObject?>(null) }
    var removing by remember { mutableStateOf<JSONObject?>(null) }
    Column(Modifier.fillMaxSize().padding(horizontal=20.dp)) {
        Text("素材库",style=MaterialTheme.typography.headlineSmall,modifier=Modifier.padding(top=12.dp,bottom=8.dp))
        Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
            FilterChip(vm.libraryKind=="image",{vm.searchLibrary("image")},label={Text("图片库")})
            FilterChip(vm.libraryKind=="video",{vm.searchLibrary("video")},label={Text("视频库")})
            TextButton(onClick={picker.launch(if(vm.libraryKind=="image")arrayOf("image/png","image/jpeg","image/webp") else arrayOf("video/mp4","video/webm"))},enabled=!vm.working){Text("导入")}
        }
        LibraryFilters(vm)
        Row(verticalAlignment=Alignment.CenterVertically) {
            OutlinedTextField(vm.search,{vm.search=it},label={Text("搜索素材")},singleLine=true,modifier=Modifier.weight(1f))
            TextButton(onClick={vm.searchLibrary()},enabled=!vm.working){Text("搜索")}
        }
        Row(verticalAlignment=Alignment.CenterVertically) {
            Text("${vm.libraryTotal} 份作品",modifier=Modifier.weight(1f).padding(vertical=12.dp),style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            if(vm.libraryTotal>40) {
                TextButton(onClick={vm.searchLibrary(offset=(vm.libraryOffset-40).coerceAtLeast(0))},enabled=vm.libraryOffset>0&&!vm.working){Text("上页")}
                TextButton(onClick={vm.searchLibrary(offset=vm.libraryOffset+40)},enabled=vm.libraryOffset+40<vm.libraryTotal&&!vm.working){Text("下页")}
            }
        }
        LazyVerticalGrid(columns=GridCells.Adaptive(155.dp),verticalArrangement=Arrangement.spacedBy(10.dp),horizontalArrangement=Arrangement.spacedBy(10.dp),contentPadding=PaddingValues(bottom=16.dp)) {
            items(vm.library,key={it.getString("file")}) { asset ->
                StudioCard {
                    AssetImage(vm,asset.optString("media"),asset.optString("name"),Modifier.fillMaxWidth().height(145.dp).clickable{vm.previewFile(asset.getString("file"))})
                    Column(Modifier.padding(8.dp)) {
                        Text(asset.optString("name"),maxLines=2,style=MaterialTheme.typography.labelLarge)
                        Text(if(asset.optString("kind")=="video")"点击播放视频" else "点击放大图片",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.primary,modifier=Modifier.clickable{vm.previewFile(asset.getString("file"))}.padding(vertical=8.dp))
                        if(!vm.libraryTrash && asset.optString("kind")=="image")OutlinedButton(onClick={vm.openGeneration("video",reference=asset.getString("file"))},enabled=vm.connected&&!vm.working,modifier=Modifier.fillMaxWidth()) { Text("用此图制作视频",style=MaterialTheme.typography.labelMedium) }
                        if(!vm.libraryTrash)Row {
                            TextButton(onClick={adopt=asset}){Text("选用")}
                            TextButton(onClick={vm.command("context.add_media",obj("file" to asset.getString("file")));vm.navigate("AI")}){Text("给 AI")}
                        }
                        TextButton(onClick={if(vm.libraryTrash)vm.action{vm.call("library.restore",obj("file" to asset.getString("file")));vm.loadLibrary(0)}else removing=asset},enabled=!vm.working,modifier=Modifier.testTag("trashMedia:${asset.getString("file")}")){Text(if(vm.libraryTrash)"恢复素材" else "移入回收站",style=MaterialTheme.typography.labelSmall)}
                    }
                }
            }
        }
    }
    removing?.let { asset -> AlertDialog(onDismissRequest={removing=null},title={Text("移入素材回收站？")},text={Text("${asset.optString("name")} 将从素材库隐藏，可在回收站恢复。正在使用或生成中的素材由 PC 检查并拒绝不合法操作。")},confirmButton={TextButton(onClick={vm.action{vm.call("library.delete",obj("file" to asset.getString("file")));vm.loadLibrary(0);removing=null}},enabled=!vm.working){Text("移入回收站")}},dismissButton={TextButton(onClick={removing=null}){Text("取消")}}) }
    adopt?.let { asset ->
        AlertDialog(onDismissRequest={adopt=null},title={Text("选用这份素材")},text={Column(Modifier.verticalScroll(rememberScrollState())) {
            if(asset.optString("kind")=="image")listOf("characters" to "添加为角色","scenes" to "添加为场景").forEach { (kind,label) ->
                TextButton(onClick={vm.command("asset.from_media",obj("kind" to kind,"file" to asset.getString("file")));adopt=null}){Text(label)}
            }
            vm.project!!.rows("shots").forEach { shot ->TextButton(onClick={vm.command("asset.use_media",obj("id" to shot.getString("id"),"file" to asset.getString("file")));adopt=null}){Text("添加到 ${shot.optString("name")}")} }
        }},confirmButton={TextButton(onClick={adopt=null}){Text("关闭")}})
    }
}
