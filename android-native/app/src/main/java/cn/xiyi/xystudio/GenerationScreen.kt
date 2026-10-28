package cn.xiyi.xystudio

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import org.json.JSONArray
import org.json.JSONObject

@Composable
private fun GenerationSection(number: String, title: String, content: @Composable ColumnScope.() -> Unit) {
    StudioCard(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface), shape = RoundedCornerShape(20.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("$number  $title", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            content()
        }
    }
}

@Composable
fun GenerationDialog(vm: StudioViewModel, initial: JSONObject) {
    val draftKey = initial.toString()
    val video = GenerationRules.isVideo(initial.optString("mode"))
    var mode by rememberSaveable(draftKey) { mutableStateOf(initial.optString("mode")) }
    var prompt by rememberSaveable(draftKey) { mutableStateOf(initial.optString("prompt")) }
    var ratio by rememberSaveable(draftKey) { mutableStateOf(initial.optString("ratio", "16:9")) }
    var mp by rememberSaveable(draftKey) { mutableStateOf(initial.optString("megapixels", "1")) }
    var seconds by rememberSaveable(draftKey) { mutableStateOf(initial.optString("seconds", "2")) }
    var steps by rememberSaveable(draftKey) { mutableStateOf(initial.optString("steps", "0")) }
    var seed by rememberSaveable(draftKey) { mutableStateOf(initial.optString("seed")) }
    var scale by rememberSaveable(draftKey) { mutableStateOf(initial.optString("scale", "2")) }
    var cinema by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("cinema")) }
    var strength by rememberSaveable(draftKey) { mutableStateOf(initial.optString("cinema_strength", "0.4")) }
    var int8 by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("qwen_int8")) }
    var follow by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("edit_follow_source", true)) }
    var quad by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("quad_lora", true)) }
    var styles by rememberSaveable(draftKey) { mutableStateOf(initial.strings("styles")) }
    var refs by rememberSaveable(draftKey) { mutableStateOf(initial.strings("references")) }
    var videoRefs by rememberSaveable(draftKey) { mutableStateOf(initial.strings("video_references")) }
    var apiModel by rememberSaveable(draftKey) { mutableStateOf(initial.optString("api_model","MiniMax-H3")) }
    var apiResolution by rememberSaveable(draftKey) { mutableStateOf(initial.optString("api_resolution","720P")) }
    var apiWatermark by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("api_watermark",false)) }
    var apiContextIr by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("api_context_ir",true)) }
    var apiLastFrame by rememberSaveable(draftKey) { mutableStateOf(initial.optBoolean("api_last_frame",true)) }
    var advanced by rememberSaveable(draftKey) { mutableStateOf(false) }
    var choosing by rememberSaveable { mutableStateOf(false) }
    var choosingVideo by rememberSaveable { mutableStateOf(false) }
    var discard by remember { mutableStateOf(false) }
    var validation by remember { mutableStateOf("") }
    var confirmed by remember { mutableStateOf<JSONObject?>(null) }
    var output by remember { mutableStateOf<JSONObject?>(null) }
    val focus = LocalFocusManager.current
    val keyboard = LocalSoftwareKeyboardController.current
    val catalog = vm.state.optJSONObject("catalog") ?: JSONObject()
    val modes = catalog.optJSONObject("modes") ?: JSONObject()
    val range = GenerationRules.referenceRange(mode)
    val cloud = GenerationRules.isCloud(mode)
    val apiCatalog=catalog.optJSONObject("pixstag") ?: JSONObject()

    fun changeMode(next: String) {
        focus.clearFocus();keyboard?.hide()
        mode=next;steps="0";validation=""
        if(GenerationRules.isCloud(next)) {
            if(seconds.toDoubleOrNull()?.let{it in 4.0..30.0 && it%1.0==0.0}!=true)seconds="5"
            if(ratio !in apiCatalog.strings("ratios"))ratio="16:9"
        } else if(ratio=="adaptive")ratio="16:9"
    }

    fun close() { vm.generation = null; vm.generationReviewId = null }
    fun value(): JSONObject {
        // Strings are validated before numeric conversion, so an empty field has a readable error.
        val g = initial.copyJson().apply {
            put("mode", mode); put("prompt", prompt.trim()); put("ratio", ratio)
            put("megapixels", mp); put("seconds", seconds); put("steps", steps); put("seed", seed)
            put("scale", scale); put("cinema_strength", strength)
            put("cinema", cinema); put("qwen_int8", int8); put("edit_follow_source", follow)
            put("quad_lora", quad); put("styles", JSONArray(styles))
            put("references", JSONArray(if (range.last == 0) emptyList<String>() else refs))
            put("video_references", JSONArray(if(mode=="pixstag_ref")videoRefs else emptyList<String>()))
            put("api_model",apiModel);put("api_resolution",apiResolution);put("api_watermark",apiWatermark)
            put("api_context_ir",apiContextIr);put("api_last_frame",apiLastFrame)
        }
        GenerationRules.validate(g)?.let { throw IllegalArgumentException(it) }
        return g.apply {
            put("megapixels", mp.toDouble()); put("seconds", seconds.toDouble()); put("steps", steps.toInt())
            put("scale", scale.toDouble()); put("cinema_strength", strength.toDouble())
        }
    }

    Dialog(onDismissRequest = { if (!vm.working) discard = true }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.imePadding()) {
                Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(if (video) "制作视频" else "创作图片", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
                        Text(if (vm.generationReviewId != null) "审阅 AI 建议后再执行" else "${vm.project?.optString("name")} · 保存到 PC 素材库", style = MaterialTheme.typography.labelSmall)
                    }
                    TextButton(onClick = { discard = true }, enabled = !vm.working) { Text("关闭") }
                }
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(horizontal = 12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    GenerationSection("01", "选择创作方式") {
                        if(video)Choice("生成来源",if(cloud)"pixstag" else "comfy",listOf("comfy" to "本地 ComfyUI","pixstag" to "Pixstag 云端 API")){changeMode(if(it=="pixstag")if(refs.isNotEmpty())"pixstag_i2v" else "pixstag_t2v" else if(refs.isNotEmpty())"h3_i2v" else "h3_t2v")}
                        Choice("工作流", mode, modes.keys().asSequence().filter { GenerationRules.isVideo(it) == video && GenerationRules.isCloud(it)==cloud }.map { it to modes.getString(it) }.toList()) {changeMode(it)}
                        if(cloud) {
                            Choice("Pixstag 模型",apiModel,apiCatalog.strings("models").map{it to it}){apiModel=it}
                            Text("由 PC 调用云端 API，可能扣除账户积分；确认后上传提示词和参考素材。",style=MaterialTheme.typography.bodySmall)
                            if(vm.state.optJSONObject("config")?.optBoolean("pixstagKeySet")!=true)Text("请先在 PC 设置保存 Pixstag API Key；手机不接收密钥。",color=MaterialTheme.colorScheme.error,style=MaterialTheme.typography.bodySmall)
                        }
                        Text(if (video) "图生视频让已有图片动起来；文生视频从文字开始。" else "直接生成新图，或选取项目图片进行编辑。", style = MaterialTheme.typography.bodySmall)
                    }
                    GenerationSection("02", if (range.last > 0) "内容与参考图片" else "描述你的创意") {
                        OutlinedTextField(prompt, { prompt = it; validation = "" }, label = { Text("提示词") },
                            placeholder = { Text(if (video) "描述主体动作、镜头运动、光线和声音…" else "描述主体、环境、构图、光线与风格…") },
                            modifier = Modifier.fillMaxWidth(), minLines = 4, maxLines = 10,
                            supportingText = { Text(if (mode == "upscale") "高清放大可不填提示词" else if (video) "保留关键动作，避免短视频承载过多变化" else "用具体描述表达你希望看到的画面") })
                        if (range.last > 0) {
                            Text(GenerationRules.referenceHint(mode), style = MaterialTheme.typography.bodySmall)
                            refs.forEachIndexed { index, file ->
                                val record = vm.references.find { it.optString("file") == file }
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    AssetImage(vm, record?.optString("media") ?: "", "参考 ${index + 1}", Modifier.size(72.dp).clickable { vm.previewFile(file) })
                                    Column(Modifier.weight(1f).padding(start = 10.dp)) {
                                        Text(if (mode in listOf("h3_fl2v","pixstag_fl2v")) if (index == 0) "首帧" else "尾帧" else "参考 ${index + 1}", style = MaterialTheme.typography.labelLarge)
                                        Text(record?.optString("name") ?: "已有项目图片", maxLines = 1, style = MaterialTheme.typography.bodySmall)
                                        Row {
                                            if (refs.size > 1) TextButton(onClick = { refs = refs.toMutableList().apply { add(index - 1, removeAt(index)) } }, enabled = index > 0) { Text("上移") }
                                            TextButton(onClick = { refs = refs.filterIndexed { i, _ -> i != index } }) { Text("移除") }
                                        }
                                    }
                                }
                            }
                            OutlinedButton(onClick = { focus.clearFocus(); keyboard?.hide(); choosing = true }, modifier = Modifier.fillMaxWidth().testTag("chooseReferences")) { Text("选择参考图片 · ${refs.size}/${range.last}") }
                            if (refs.size > range.last) Text("切换工作流后请移除多余参考图", color = MaterialTheme.colorScheme.error)
                        }
                        if(mode=="pixstag_ref") {
                            Text("参考视频 · MP4，每个不超过 5 MB",style=MaterialTheme.typography.labelLarge)
                            videoRefs.forEachIndexed { index,file ->
                                Row(verticalAlignment=Alignment.CenterVertically) {
                                    Text(vm.references.find{it.optString("file")==file}?.optString("name") ?: "参考视频 ${index+1}",Modifier.weight(1f))
                                    TextButton(onClick={videoRefs=videoRefs-file}){Text("移除")}
                                }
                            }
                            OutlinedButton(onClick={focus.clearFocus();keyboard?.hide();choosingVideo=true},modifier=Modifier.fillMaxWidth().testTag("chooseVideoReferences")){Text("选择参考视频 · ${videoRefs.size}/3")}
                        }
                    }
                    GenerationSection("03", "输出设置") {
                        if (mode == "qwen_edit") Row(verticalAlignment = Alignment.CenterVertically) {
                            Switch(follow, { follow = it }); Text("沿用参考图尺寸", Modifier.padding(start = 10.dp))
                        }
                        if (mode != "upscale" && !(mode == "qwen_edit" && follow)) {
                            Text("画面比例", style = MaterialTheme.typography.labelMedium)
                            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                listOf("16:9" to "横屏 16:9", "9:16" to "竖屏 9:16", "1:1" to "方形 1:1").forEach { (id, label) ->
                                    FilterChip(ratio == id, { ratio = id }, label = { Text(label) })
                                }
                            }
                            Choice("更多比例", ratio, (if(cloud)apiCatalog else catalog).strings("ratios").map { it to it }) { ratio = it }
                            if(cloud)Choice("清晰度",apiResolution,apiCatalog.strings("resolutions").map{it to it}){apiResolution=it}
                            else {
                                NumericField("像素量 MP", mp, { mp = it })
                                Text("像素量越高，对 PC 显存与时间的要求越高。", style = MaterialTheme.typography.bodySmall)
                            }
                        }
                        if (video) {
                            NumericField("视频秒数", seconds, { seconds = it })
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                (if(cloud)listOf("5","10","15") else listOf("2", "5", "10")).forEach { s -> FilterChip(seconds.toDoubleOrNull() == s.toDouble(), { seconds = s }, label = { Text("$s 秒") }) }
                            }
                            Text(if(cloud)"4–30 整数秒；最终规格以 Pixstag 返回的结果为准。" else "最终时长按 PC 工作流的帧数规则对齐，下一步显示实际输出。", style = MaterialTheme.typography.bodySmall)
                        }
                        if (mode == "upscale") NumericField("放大倍率", scale, { scale = it })
                    }
                    if(cloud)GenerationSection("04","云端选项") {
                        Row(verticalAlignment=Alignment.CenterVertically){Checkbox(apiContextIr,{apiContextIr=it});Text("Context-IR 提示词优化")}
                        Row(verticalAlignment=Alignment.CenterVertically){Checkbox(apiWatermark,{apiWatermark=it});Text("AIGC 标识水印")}
                        Row(verticalAlignment=Alignment.CenterVertically){Checkbox(apiLastFrame,{apiLastFrame=it});Text("请求返回尾帧")}
                        Text("已提交任务无取消接口；停止本机查询也不会停止云端生成或计费。大于 3 MB 的图片会压缩上传副本，PC 原图保留。",style=MaterialTheme.typography.bodySmall)
                    } else GenerationSection("04", "采样与高级选项") {
                        NumericField("采样步数 (0 自动)", steps, { steps = it })
                        Text("0 使用 PC 工作流默认步数；低步数适合快速测试。", style = MaterialTheme.typography.bodySmall)
                        TextButton(onClick = { advanced = !advanced }, modifier = Modifier.testTag("advancedParameters")) { Text(if (advanced) "收起高级参数" else "展开高级参数 · 种子 / 模型选项") }
                        if (advanced) {
                            NumericField("种子", seed, { seed = it })
                            TextButton(onClick = { vm.action { seed = vm.call("generation.seed").toString() } }, enabled = !vm.working) { Text("换一个随机种子") }
                            if (mode.startsWith("qwen")) Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(int8, { int8 = it }); Text("使用 INT8 模型") }
                            if (video) {
                                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(cinema, { cinema = it }); Text("电影 LoRA") }
                                if (cinema) NumericField("电影 LoRA 强度", strength, { strength = it })
                            }
                            if (mode == "quad") Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(quad, { quad = it }); Text("四视图 LoRA") }
                            if (mode == "krea") catalog.optJSONObject("styles")?.keys()?.asSequence()?.toList()?.forEach { key ->
                                Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(key in styles, { styles = if (it) styles + key else styles - key }); Text(key) }
                            }
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                }
                Surface(shadowElevation = 6.dp) {
                    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        val issue = validation.ifEmpty { vm.error }.ifEmpty { if (!vm.connected) "PC 连接已断开，请恢复连接后继续" else "" }
                        if (issue.isNotEmpty()) Text(issue, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                        Button(onClick = {
                            focus.clearFocus();keyboard?.hide()
                            try {
                                val g = value(); validation = ""
                                vm.action { output = vm.call("generation.preview", obj("generation" to g)) as JSONObject; confirmed = g }
                            } catch (e: IllegalArgumentException) { validation = e.message ?: "请检查参数" }
                        }, enabled = !vm.working && vm.connected, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("reviewGeneration")) {
                            Text(if (vm.working) "正在核对 PC 参数…" else "下一步 · 确认生成")
                        }
                    }
                }
            }
        }
    }
    if (choosing) ReferencePicker(vm, refs, range.last, { refs = it }, { choosing = false })
    if (choosingVideo) ReferencePicker(vm, videoRefs, 3, { videoRefs=it }, { choosingVideo=false },kind="video")
    if (discard) AlertDialog(onDismissRequest = { discard = false }, title = { Text("离开生成编辑？") },
        text = { Text("当前未提交的参数将被放弃，PC 中的项目和任务不受影响。") },
        confirmButton = { TextButton(onClick = { close() }) { Text("放弃并关闭") } },
        dismissButton = { TextButton(onClick = { discard = false }) { Text("继续编辑") } })
    confirmed?.let { g ->
        AlertDialog(onDismissRequest = { if (!vm.working) confirmed = null }, title = { Text("确认生成${if (video) "视频" else "图片"}") },
            text = {
                Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(modes.optString(g.optString("mode")), fontWeight = FontWeight.Bold)
                    if(cloud) {
                        Text("${g.optString("api_model")} · ${g.optString("api_resolution")} · ${g.optString("ratio")} · ${g.optDouble("seconds").toInt()} 秒",style=MaterialTheme.typography.titleMedium)
                        Text(output?.optString("notice") ?: "确认调用 Pixstag，可能消耗账户积分。",color=MaterialTheme.colorScheme.primary)
                        Text("参考图片 ${g.strings("references").size} 张 · 视频 ${g.strings("video_references").size} 个")
                        output?.rows("references")?.filter{it.optBoolean("converted")}?.let{if(it.isNotEmpty())Text("${it.size} 张图片将使用转换压缩副本上传。")}
                    } else {
                        Text("${output?.optInt("width")} × ${output?.optInt("height")} · ${output?.optInt("steps")} 步", style = MaterialTheme.typography.titleMedium)
                        if (video) Text("${output?.optInt("frames")} 帧 / 24 fps · 实际约 ${"%.2f".format(output?.optDouble("seconds"))} 秒")
                        Text("参考图片 ${g.strings("references").size} 张 · 种子 ${g.optString("seed")}", style = MaterialTheme.typography.bodySmall)
                    }
                    Text(g.optString("prompt"), maxLines = 8)
                    Text("结果保存到「${vm.project?.optString("name") }」的${if (video) "视频库" else "图片库"}。提交后可在任务页查看真实进度。", style = MaterialTheme.typography.bodySmall)
                    if (vm.project?.optBoolean("paused") == true) Text("PC 队列已暂停，任务将等待队列继续。", color = MaterialTheme.colorScheme.error)
                    if (vm.error.isNotEmpty()) Text(vm.error, color = MaterialTheme.colorScheme.error)
                }
            },
            confirmButton = { Button(onClick = { vm.submitGeneration(g) }, enabled = vm.connected && !vm.working && (!cloud || output?.optBoolean("keySet")==true), modifier = Modifier.testTag("submitGeneration")) { Text(if (vm.working) "正在提交…" else if(cloud)"确认调用 Pixstag（可能扣费）" else "确认并加入 PC 队列") } },
            dismissButton = { TextButton(onClick = { confirmed = null }, enabled = !vm.working) { Text("返回修改") } })
    }
}

@Composable
private fun ReferencePicker(vm: StudioViewModel, selected: List<String>, maximum: Int, change: (List<String>) -> Unit, close: () -> Unit,kind:String="image") {
    var query by rememberSaveable { mutableStateOf("") }
    val images = vm.references.filter { it.optString("kind")==kind && (kind!="video" || it.optString("file").endsWith(".mp4",true)) && it.optString("name").contains(query, ignoreCase = true) }
    Dialog(onDismissRequest = close, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding()) {
            Column(Modifier.imePadding().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(if(kind=="video")"选择项目视频" else "选择项目图片", style = MaterialTheme.typography.headlineSmall)
                Text("已选 ${selected.size}/$maximum · 按选择顺序排列", style = MaterialTheme.typography.bodySmall)
                OutlinedTextField(query, { query = it }, label = { Text("搜索参考图片") }, singleLine = true, modifier = Modifier.fillMaxWidth())
                if (selected.size >= maximum) Text("已达数量上限，先取消一张再选择其他图片。", style = MaterialTheme.typography.bodySmall)
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (images.isEmpty()) item { Text(if (vm.references.isEmpty()) "项目还没有图片，请先生成图片或在素材库导入。" else "没有找到匹配图片") }
                    items(images, key = { it.getString("file") }) { record ->
                        val file = record.getString("file")
                        val index = selected.indexOf(file)
                        val enabled = index >= 0 || selected.size < maximum
                        StudioCard(Modifier.fillMaxWidth().testTag("reference:$file").clickable(enabled = enabled) { change(if (index >= 0) selected - file else selected + file) },
                            colors = CardDefaults.cardColors(containerColor = if (index >= 0) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant)) {
                            Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                                AssetImage(vm, record.optString("media"), record.optString("name"), Modifier.size(76.dp))
                                Text(record.optString("name"), Modifier.weight(1f).padding(12.dp), maxLines = 2)
                                Text(if (index >= 0) "已选 ${index + 1}" else "选择", style = MaterialTheme.typography.labelMedium)
                            }
                        }
                    }
                }
                Button(onClick = close, modifier = Modifier.fillMaxWidth().testTag("finishReferences")) { Text("完成选择 (${selected.size})") }
            }
        }
    }
}
