package cn.xiyi.xystudio

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import org.json.JSONArray
import org.json.JSONObject

@Composable fun Choice(label:String,value:String,options:List<Pair<String,String>>,onChange:(String)->Unit) {
    var expanded by remember { mutableStateOf(false) }
    Column {
        Text(label,style=MaterialTheme.typography.labelMedium)
        Box {
            OutlinedButton(onClick={expanded=true},modifier=Modifier.fillMaxWidth()){Text(options.find{it.first==value}?.second ?: value)}
            DropdownMenu(expanded,onDismissRequest={expanded=false}) {
                options.forEach { (id,title) -> DropdownMenuItem(text={Text(title)},onClick={onChange(id);expanded=false}) }
            }
        }
    }
}
@Composable fun NumericField(label:String,value:String,onChange:(String)->Unit,modifier:Modifier=Modifier) {
    OutlinedTextField(value,onChange,label={Text(label)},singleLine=true,keyboardOptions=KeyboardOptions(keyboardType=KeyboardType.Decimal),modifier=modifier.fillMaxWidth())
}

private val statusNames=mapOf("new" to "等待提交","submitting" to "正在提交","queued" to "后端排队中","running" to "正在生成","downloading" to "保存结果到 PC","completed" to "已完成","cancelled" to "已取消","cancel_requested" to "正在取消","failed" to "失败","unknown" to "状态未知，需核对","detached" to "查询已中断")
@Composable fun TasksScreen(vm:StudioViewModel) {
    if(EmptyProject(vm))return
    var filter by remember { mutableStateOf("all") }
    var cancelling by remember { mutableStateOf<JSONObject?>(null) }
    var details by remember { mutableStateOf<JSONObject?>(null) }
    val scroll=rememberLazyListState()
    LaunchedEffect(vm.submissionCount) { filter="all";scroll.scrollToItem(0) }
    val activeStatuses=setOf("new","submitting","queued","running","downloading","cancel_requested")
    val allTasks=vm.project!!.rows("tasks").reversed()
    val tasks=allTasks.filter{filter=="all"||if(filter=="active")it.optString("status") in activeStatuses else it.optString("status")==filter}
    LazyColumn(state=scroll,contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        item { Text("任务与生成历史",style=MaterialTheme.typography.headlineSmall) }
        item { Text("${allTasks.count{it.optString("status") in activeStatuses}} 个进行中 · ${allTasks.count{it.optString("status")=="completed"}} 个已完成",style=MaterialTheme.typography.bodyMedium) }
        item { Row(verticalAlignment=Alignment.CenterVertically) {
            TextButton(onClick={vm.command("queue.toggle")},enabled=!vm.working){Text(if(vm.project!!.optBoolean("paused"))"继续后续队列" else "暂停后续队列")}
            Text("${tasks.size} 条",style=MaterialTheme.typography.labelSmall)
        } }
        item { Choice("筛选",filter,listOf("all" to "全部", "active" to "进行中 / 排队","completed" to "已完成","failed" to "失败","cancelled" to "已取消","unknown" to "状态未知","detached" to "查询中断")){filter=it} }
        if(tasks.isEmpty())item { Text("这里还没有任务。点击上方生成按钮开始创作。",Modifier.padding(vertical=24.dp)) }
        items(tasks,key={it.getString("id")}) { task ->
            val status=task.optString("status")
            StudioCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                    Text(task.optString("targetName"),style=MaterialTheme.typography.titleMedium)
                    val g=task.optJSONObject("generation")
                    val cloud=GenerationRules.isCloud(g?.optString("mode") ?: "")
                    val remoteId=task.optString("remoteId","").takeUnless{it=="null"} ?: ""
                    Text("${if(task.optString("kind")=="video")"视频" else "图片"} · ${vm.state.optJSONObject("catalog")?.optJSONObject("modes")?.optString(g?.optString("mode") ?: "") ?: ""}",style=MaterialTheme.typography.labelMedium)
                    Text(statusNames[status] ?: status,color=MaterialTheme.colorScheme.primary)
                    if(!task.isNull("progress")) {
                        val progress=(task.optDouble("progress")/100).toFloat().coerceIn(0f,1f)
                        LinearProgressIndicator(progress={progress},modifier=Modifier.fillMaxWidth())
                        Text("节点 ${task.optString("node")} · ${(progress*100).toInt()}%（当前节点，不是总体进度）",style=MaterialTheme.typography.labelSmall)
                    } else if(status in listOf("running","queued","submitting","downloading")) {
                        LinearProgressIndicator(Modifier.fillMaxWidth())
                        Text(if(cloud)"Pixstag 仅返回任务阶段，不提供总体百分比。" else "PC 尚未返回节点步数，不估算百分比。",style=MaterialTheme.typography.labelSmall)
                    }
                    Text(task.optString("prompt"),maxLines=5,style=MaterialTheme.typography.bodySmall)
                    if(cloud)Text("Pixstag · ${g?.optString("api_model")} · 任务 ID：${remoteId.ifEmpty{"尚未取得"}}。已提交任务无取消接口，停止查询不停止计费。",style=MaterialTheme.typography.bodySmall)
                    TextButton(onClick={details=task}){Text("查看完整参数")}
                    if(task.optString("error").isNotBlank()&&task.optString("error")!="null")Text(task.optString("error"),color=MaterialTheme.colorScheme.error,style=MaterialTheme.typography.bodySmall)
                    task.rows("results").forEach { v ->
                        AssetImage(vm,v.optString("media"),"生成结果",Modifier.fillMaxWidth().height(190.dp).clickable{vm.previewFile(v.getString("file"))})
                        TextButton(onClick={vm.previewFile(v.getString("file"))}){Text(if(v.optString("kind")=="video")"播放生成视频" else "查看生成图片")}
                        if(v.optString("kind")=="image")OutlinedButton(onClick={vm.openGeneration("video",reference=v.getString("file"))},enabled=vm.connected&&!vm.working,modifier=Modifier.testTag("imageToVideo:${v.getString("file")}")){Text("用此图制作视频")}
                    }
                    Row(Modifier.horizontalScroll(rememberScrollState())) {
                        if(task.optBoolean("canCancel",!cloud&&status in listOf("new","queued","running")))TextButton(onClick={cancelling=task},enabled=!vm.working&&vm.connected){Text("取消任务")}
                        if(task.optBoolean("canDetach"))TextButton(onClick={vm.command("task.detach",obj("id" to task.getString("id")))},enabled=!vm.working&&vm.connected){Text("停止本机查询（云端继续）")}
                        if(status in listOf("unknown","detached","queued","running","failed") && vm.state.optString("activeJob")!=task.optString("id"))TextButton(onClick={vm.command("task.resume",obj("id" to task.getString("id")))},enabled=!vm.working&&(!cloud||remoteId.isNotEmpty())){Text("恢复查询")}
                        TextButton(onClick={vm.openGeneration(task.optString("kind"),task.optJSONObject("generation"))},enabled=!vm.working&&!(cloud&&status=="unknown"&&remoteId.isEmpty())){Text("审阅后再次生成")}
                    }
                    Text(task.optString("time").take(19),style=MaterialTheme.typography.labelSmall)
                }
            }
        }
    }
    details?.let { task -> AlertDialog(onDismissRequest={details=null},title={Text("任务参数")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(8.dp)) {
        androidx.compose.foundation.text.selection.SelectionContainer { Text(task.optString("prompt")) }
        task.optJSONObject("generation")?.let { g ->
            (if(GenerationRules.isCloud(g.optString("mode")))listOf("mode" to "方式","api_model" to "模型","api_resolution" to "清晰度","ratio" to "比例","seconds" to "请求秒数","api_context_ir" to "提示词优化","api_watermark" to "水印","api_last_frame" to "请求尾帧") else listOf("mode" to "工作流","ratio" to "比例","megapixels" to "像素量 MP","seconds" to "请求秒数","steps" to "步数","seed" to "种子","scale" to "放大倍率","cinema" to "电影风格","cinema_strength" to "电影风格强度","qwen_int8" to "INT8","edit_follow_source" to "跟随参考尺寸","quad_lora" to "四视图 LoRA")).forEach { (key,label) -> if(g.has(key))Text("$label：${g.optString(key)}") }
            Text("参考图片：${g.strings("references").size} 张")
            if(GenerationRules.isCloud(g.optString("mode")))Text("参考视频：${g.strings("video_references").size} 个")
        }
    }},confirmButton={TextButton(onClick={details=null}){Text("关闭")}}) }
    cancelling?.let { task -> AlertDialog(onDismissRequest={cancelling=null},title={Text("取消这个任务？")},text={Text("${task.optString("targetName")} 将向 PC 请求取消；已经保存的结果会保留。")},confirmButton={TextButton(onClick={vm.command("task.cancel",obj("id" to task.getString("id")));cancelling=null}){Text("确认取消")}},dismissButton={TextButton(onClick={cancelling=null}){Text("继续生成")}}) }
}

@Composable fun AssistantScreen(vm:StudioViewModel) {
    if(EmptyProject(vm))return
    val text = vm.chatDraft
    var settingsExpanded by rememberSaveable { mutableStateOf(false) }
    val config=vm.state.optJSONObject("config") ?: JSONObject()
    val chatScroll=rememberLazyListState()
    val chatCount=vm.project!!.rows("chat").size
    val contextCount=0
    LaunchedEffect(chatCount,vm.review?.optString("id")) {
        val count=chatCount+contextCount+if(vm.review!=null)1 else 0
        if(count>0)chatScroll.animateScrollToItem(count-1)
    }
    Column(Modifier.fillMaxSize().imePadding()) {
        Column(Modifier.padding(horizontal=16.dp)) {
            Row(verticalAlignment=Alignment.CenterVertically) {
                Text(config.optString("model"),style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.weight(1f))
                TextButton(onClick={settingsExpanded=!settingsExpanded}){Text(if(settingsExpanded)"收起设置" else "对话设置")}
            }
            if(settingsExpanded) {
                Choice("DeepSeek 模型",config.optString("model"),config.strings("models").map{it to it}){vm.command("settings.save",obj("model" to it))}
                Row(verticalAlignment=Alignment.CenterVertically){Checkbox(config.optBoolean("online"),{vm.command("settings.save",obj("online" to it))});Text("允许联网检索",style=MaterialTheme.typography.bodySmall);TextButton(onClick={vm.command("models.refresh")}){Text("刷新模型")}}
            }
            if(!config.optBoolean("keySet"))Text("请先在 PC 桌面设置 DeepSeek API Key；手机不接收密钥。",color=MaterialTheme.colorScheme.error,style=MaterialTheme.typography.bodySmall)
        }
        LazyColumn(Modifier.weight(1f),state=chatScroll,contentPadding=PaddingValues(16.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            if(chatCount==0 && vm.review==null)item {
                Column(Modifier.fillMaxWidth().padding(top=32.dp,bottom=20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
                    StudioIcon("AI",Modifier.size(36.dp),MaterialTheme.colorScheme.primary)
                    Text("一起把想法变成画面",style=MaterialTheme.typography.titleLarge)
                    Text("讨论故事、完善角色，或为下一段镜头寻找灵感。",style=MaterialTheme.typography.bodyMedium,color=MaterialTheme.colorScheme.onSurfaceVariant)
                    listOf("帮我梳理故事大纲","设计一个角色","完善这段分镜").forEach { suggestion ->
                        OutlinedButton(onClick={vm.chatDraft=suggestion},modifier=Modifier.fillMaxWidth()){Text(suggestion)}
                    }
                    Text("点选填入输入框，确认后发送。",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            items(vm.project!!.rows("chat"),key={it.getString("id")}) { message ->
                StudioCard(colors=CardDefaults.cardColors(containerColor=if(message.optString("role")=="user") MaterialTheme.colorScheme.primaryContainer else Color.White)) {
                    Column(Modifier.padding(14.dp)) {
                        Text(when(message.optString("role")){"user"->"你";"tool"->"操作结果";else->"AI 助手"},style=MaterialTheme.typography.labelLarge)
                        androidx.compose.foundation.text.selection.SelectionContainer { Text(message.optString("text")) }
                        ChatSources(message)
                    }
                }
            }
            vm.review?.let { review -> item {
                StudioCard(colors=CardDefaults.cardColors(containerColor=Color(0xFFFFF4DC))) {
                    Column(Modifier.padding(14.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                        Text("需要你的确认 · ${review.optString("title")}",style=MaterialTheme.typography.titleMedium)
                        val args=review.optJSONObject("args") ?: JSONObject()
                        listOf("name","description","text","prompt").forEach { key ->if(args.has(key))Text(args.optString(key)) }
                        review.optJSONObject("media")?.let { AssetImage(vm,it.optString("url"),"建议使用的素材",Modifier.height(160.dp).fillMaxWidth()) }
                        Text("Skill 由 PC 加载，项目修改与生成均经此审阅。",style=MaterialTheme.typography.bodySmall)
                        Row {
                            TextButton(onClick={vm.command("review.respond",obj("id" to review.getString("id"),"accepted" to false))},enabled=!vm.working){Text("拒绝")}
                            Button(onClick={if(review.optString("name")=="generate")vm.openGeneration("image",review.getJSONObject("generation"),review.getString("id"))else vm.command("review.respond",obj("id" to review.getString("id"),"accepted" to true))},enabled=!vm.working){Text(if(review.optString("name")=="generate")"审阅生成参数" else "确认修改")}
                        }
                    }
                }
            } }
            if(vm.state.optBoolean("busy"))item { Text("${vm.state.optString("status")} · 请完成本轮对话或审阅",style=MaterialTheme.typography.bodySmall) }
        }
        ChatAttachments(vm)
        Row(Modifier.padding(horizontal=12.dp,vertical=6.dp),verticalAlignment=Alignment.Bottom) {
            OutlinedTextField(text,{vm.chatDraft=it},label={Text("和 AI 讨论当前项目")},modifier=Modifier.weight(1f),maxLines=6)
            TextButton(onClick={val sent=text;vm.action{vm.call("chat.send",obj("text" to sent));vm.chatDraft=""}},enabled=text.isNotBlank()&&!vm.state.optBoolean("busy")&&!vm.working&&vm.connected){Text("发送")}
        }
    }
}
