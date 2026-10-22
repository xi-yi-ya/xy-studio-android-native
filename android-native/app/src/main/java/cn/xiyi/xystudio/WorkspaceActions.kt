package cn.xiyi.xystudio

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import org.json.JSONArray
import org.json.JSONObject

@Composable fun NewAssetButton(vm:StudioViewModel,kind:String) {
    var open by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    val label=if(kind=="characters")"角色" else "场景"
    OutlinedButton(onClick={open=true},enabled=vm.connected&&!vm.working){Text("新建$label")}
    if(open)AlertDialog(onDismissRequest={open=false},title={Text("新建$label")},text={Column(verticalArrangement=Arrangement.spacedBy(12.dp)) {
        OutlinedTextField(name,{name=it.take(100)},label={Text("名称")},modifier=Modifier.testTag("newAssetName"))
        OutlinedTextField(description,{description=it},label={Text("描述")},minLines=3,maxLines=6)
        Text("可以先写设定，再生成或选用图片。",style=MaterialTheme.typography.bodySmall)
    }},confirmButton={TextButton(onClick={vm.action{vm.call("asset.add",obj("kind" to kind,"name" to name.trim(),"description" to description));open=false;name="";description=""}},enabled=name.isNotBlank()&&!vm.working){Text("创建")}},dismissButton={TextButton(onClick={open=false}){Text("取消")}})
}

@Composable fun WorkspaceActions(vm:StudioViewModel,item:JSONObject,shot:Boolean=false) {
    var menu by remember { mutableStateOf(false) }
    var choosing by remember { mutableStateOf<String?>(null) }
    var linking by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf(false) }
    val id=item.getString("id")
    if(item.optBoolean("needsReview"))Text("关联内容已变化，请检查当前版本",color=MaterialTheme.colorScheme.error,style=MaterialTheme.typography.bodySmall)
    if(shot) {
        val linked=vm.project!!.rows("assets").filter{it.optString("id") in item.strings("assetIds")}
        Text(if(linked.isEmpty())"尚未关联角色或场景" else "关联："+linked.joinToString("、"){it.optString("name")},style=MaterialTheme.typography.bodySmall)
    }
    Column {
        Box {
            TextButton(onClick={menu=true},modifier=Modifier.testTag("moreAsset:$id")){Text("更多操作")}
            DropdownMenu(menu,onDismissRequest={menu=false}) {
                DropdownMenuItem(text={Text("选择 / 替换图片")},onClick={choosing="image";menu=false})
                if(shot) {
                    DropdownMenuItem(text={Text("选择 / 替换视频")},onClick={choosing="video";menu=false})
                    DropdownMenuItem(text={Text("关联角色与场景")},onClick={linking=true;menu=false})
                }
                if(item.optBoolean("needsReview"))DropdownMenuItem(text={Text("标记已检查")},onClick={vm.command("asset.reviewed",obj("id" to id));menu=false})
                DropdownMenuItem(text={Text("删除条目",color=MaterialTheme.colorScheme.error)},onClick={deleting=true;menu=false})
            }
        }
        Row(Modifier.horizontalScroll(rememberScrollState())) {
        TextButton(onClick={vm.openGeneration("image",target=id)},enabled=vm.connected&&!vm.working){Text("生成图片")}
        if(shot)TextButton(onClick={vm.openGeneration("video",target=id)},enabled=vm.connected&&!vm.working){Text("生成视频")}
        }
    }
    choosing?.let { kind -> ProjectMediaPicker(vm,title=if(kind=="video")"选择分镜视频" else "选择条目图片",initialKind=kind,allowVideo=shot,close={choosing=null}) { media ->
        vm.action { vm.call("asset.use_media",obj("id" to id,"file" to media.getString("file")));choosing=null }
    } }
    if(linking)LinkAssetsDialog(vm,item){linking=false}
    if(deleting)AlertDialog(onDismissRequest={deleting=false},title={Text("删除「${item.optString("name") }」？")},text={Text("这会从项目移除条目及其关联。已有素材文件保留在 PC 素材库中；此操作不能在手机撤销。")},confirmButton={TextButton(onClick={vm.action{vm.call("asset.delete",obj("id" to id));deleting=false}},enabled=!vm.working){Text("确认删除",color=MaterialTheme.colorScheme.error)}},dismissButton={TextButton(onClick={deleting=false}){Text("保留")}})
}

@Composable private fun LinkAssetsDialog(vm:StudioViewModel,shot:JSONObject,close:()->Unit) {
    var selected by remember { mutableStateOf(shot.strings("assetIds")) }
    val revision=remember { vm.revision }
    AlertDialog(onDismissRequest=close,title={Text("关联角色与场景")},text={Column(Modifier.verticalScroll(rememberScrollState())) {
        if(vm.project!!.rows("assets").isEmpty())Text("先创建角色或场景，再关联到分镜。")
        vm.project!!.rows("assets").forEach { asset ->
            val id=asset.getString("id")
            Row(verticalAlignment=Alignment.CenterVertically) {
                Checkbox(id in selected,{selected=if(it)selected+id else selected-id},modifier=Modifier.testTag("linkAsset:$id"))
                Text(asset.optString("name"))
            }
        }
    }},confirmButton={TextButton(onClick={vm.action{vm.call("asset.link",obj("id" to shot.getString("id"),"ids" to JSONArray(selected)),revision);close()}},enabled=!vm.working){Text("保存关联")}},dismissButton={TextButton(onClick=close){Text("取消")}})
}

@Composable fun ChatSources(message:JSONObject) {
    val activity=message.rows("activity")
    val sources=activity.filter{it.optString("type")=="search"}.flatMap{it.rows("sources")}.filter{it.optString("url").let{u->u.startsWith("https://")||u.startsWith("http://")}}.distinctBy{it.optString("url")}
    val uri=androidx.compose.ui.platform.LocalUriHandler.current
    if(activity.any{it.optString("type")=="error"})Text("部分辅助资料未能取得，以操作确认和生成记录为准。",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.error)
    sources.forEach { source ->TextButton(onClick={runCatching{uri.openUri(source.getString("url"))}}){Text(source.optString("title").ifBlank{"查看来源"},maxLines=2)} }
}
