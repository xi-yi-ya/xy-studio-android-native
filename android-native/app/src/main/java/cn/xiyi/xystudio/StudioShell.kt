package cn.xiyi.xystudio

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import org.json.JSONObject

private val activeTaskStates = setOf("new", "submitting", "queued", "running", "downloading", "cancel_requested")

@Composable
fun StudioApp(vm: StudioViewModel) {
    var connectionSettings by rememberSaveable { mutableStateOf(false) }
    val assistant = vm.page == "AI"
    val section = when(vm.page) { "角色", "场景", "分镜" -> "创作"; "项目" -> "首页"; else -> vm.page }
    BackHandler(enabled = connectionSettings || assistant || vm.page == "项目") {
        when { connectionSettings -> connectionSettings = false; assistant -> vm.navigate(vm.assistantReturnPage); else -> vm.navigate("首页") }
    }
    Scaffold(
        containerColor = MaterialTheme.colorScheme.background,
        topBar = {
            Row(Modifier.statusBarsPadding().fillMaxWidth().padding(horizontal = 20.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                if (assistant || vm.page == "项目") IconButton(onClick = { vm.navigate(if(assistant) vm.assistantReturnPage else "首页") }, modifier = Modifier.testTag("backToWorkspace")) { StudioIcon("back") }
                Column(Modifier.weight(1f)) {
                    Text(if(assistant) "AI 创作助手" else "XY STUDIO", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                    Text(if(assistant) vm.project?.optString("name") ?: "创作对话" else "MOBILE / 创作空间", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                if (!assistant) Surface(onClick = { connectionSettings = !connectionSettings }, shape = RoundedCornerShape(30.dp), color = if(vm.connected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant) {
                    Row(Modifier.padding(horizontal = 12.dp, vertical = 9.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        StudioIcon("connection", Modifier.size(16.dp), if(vm.connected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.secondary)
                        Text(if(vm.connected) "PC 已连接" else if(vm.hasAuthorization) "正在重连" else "连接 PC", style = MaterialTheme.typography.labelMedium)
                    }
                }
            }
        },
        bottomBar = {
            if (vm.hasAuthorization && !assistant && !connectionSettings) {
                Column(Modifier.background(MaterialTheme.colorScheme.surface)) {
                    HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    NavigationBar(containerColor = MaterialTheme.colorScheme.surface, tonalElevation = 0.dp, windowInsets = WindowInsets(0,0,0,0), modifier = Modifier.navigationBarsPadding().height(76.dp)) {
                        listOf("首页", "创作", "素材", "任务").forEach { name ->
                            NavigationBarItem(selected = section == name, onClick = { vm.navigate(name) }, modifier = Modifier.testTag("nav:$name"),
                                icon = { StudioIcon(name) }, label = { Text(name) },
                                colors = NavigationBarItemDefaults.colors(selectedIconColor = MaterialTheme.colorScheme.primary, selectedTextColor = MaterialTheme.colorScheme.primary, indicatorColor = MaterialTheme.colorScheme.primaryContainer))
                        }
                    }
                }
            }
        },
        floatingActionButton = {
            if(section == "创作" && vm.hasAuthorization && !connectionSettings && vm.project != null) {
                ExtendedFloatingActionButton(onClick = { vm.navigate("AI") }, icon = { StudioIcon("AI") }, text = { Text("AI 助手") },
                    containerColor = MaterialTheme.colorScheme.primary, contentColor = MaterialTheme.colorScheme.onPrimary,
                    modifier = Modifier.testTag("openAssistant"), elevation = FloatingActionButtonDefaults.elevation(defaultElevation = 3.dp))
            }
        }
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            if(vm.working) LinearProgressIndicator(Modifier.fillMaxWidth())
            if(vm.error.isNotEmpty()) StudioCard(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                Row(Modifier.padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text(vm.error, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer)
                    TextButton(onClick = { vm.error = "" }) { Text("收起") }
                }
            }
            if(!vm.hasAuthorization || connectionSettings) ConnectionScreen(vm) { connectionSettings = false }
            else when(vm.page) {
                "首页" -> HomeScreen(vm)
                "项目" -> ProjectsScreen(vm)
                "创作", "角色", "场景", "分镜" -> CreationWorkspace(vm)
                "素材" -> LibraryScreen(vm)
                "任务" -> TasksScreen(vm)
                "AI" -> AssistantScreen(vm)
            }
        }
    }
    vm.generation?.let { GenerationDialog(vm, it) }
    vm.preview?.let { MediaDialog(vm, it) }
}

@Composable
private fun GenerationEntries(vm: StudioViewModel) {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        listOf("image" to "生成图片", "video" to "生成视频").forEach { (kind, title) ->
            StudioCard(Modifier.weight(1f).testTag("generate:$kind").clickable(enabled = vm.connected && !vm.working && vm.project != null) { vm.openGeneration(kind) }) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Surface(shape = RoundedCornerShape(12.dp), color = MaterialTheme.colorScheme.primaryContainer) { StudioIcon(kind, Modifier.padding(10.dp), MaterialTheme.colorScheme.primary) }
                    Text(title, style = MaterialTheme.typography.titleMedium)
                    Text(if(kind == "image") "文生图 · 图片编辑" else "图生视频 · 参考生成", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun HomeScreen(vm: StudioViewModel) {
    val project = vm.project
    val tasks = project?.rows("tasks") ?: emptyList()
    val active = tasks.filter { it.optString("status") in activeTaskStates }
    val latest = tasks.asReversed().flatMap { it.rows("results") }.distinctBy { it.optString("file") }.take(6)
    LazyColumn(Modifier.fillMaxSize().testTag("homeContent"), contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 24.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        item {
            Text("创作工作台", style = MaterialTheme.typography.headlineSmall)
            Text("让灵感成为看得见的故事", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 4.dp))
        }
        item {
            StudioCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        StudioIcon("项目", tint = MaterialTheme.colorScheme.primary)
                        Text("当前项目", Modifier.weight(1f).padding(start = 8.dp), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        TextButton(onClick = { vm.navigate("项目") }, modifier = Modifier.testTag("manageProjects")) { Text("切换") }
                    }
                    Text(project?.optString("name") ?: "从一个项目开始", style = MaterialTheme.typography.titleLarge, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if(project != null) {
                        Text("角色 ${project.rows("assets").count { it.optString("kind") == "characters" }}  ·  场景 ${project.rows("assets").count { it.optString("kind") == "scenes" }}  ·  分镜 ${project.rows("shots").size}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else Text("打开已有项目，整理素材并开始创作。", style = MaterialTheme.typography.bodyMedium)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                        TextButton(onClick = { vm.navigate(if(project == null) "项目" else "创作") }) {
                            Text(if(project == null) "选择项目" else "进入项目"); Spacer(Modifier.width(8.dp)); StudioIcon("arrow", Modifier.size(18.dp))
                        }
                    }
                }
            }
        }
        item { GenerationEntries(vm) }
        if(active.isNotEmpty()) item { ActiveTaskCard(vm, active.firstOrNull { it.optString("id") == vm.state.optString("activeJob") } ?: active.first(), active.size) }
        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("最近作品", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                TextButton(onClick = { vm.navigate("素材") }) { Text("查看全部") }
            }
            if(latest.isEmpty()) StudioCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("你的第一份作品，从这里开始", style = MaterialTheme.typography.bodyMedium)
                    Text("生成的图片和视频会出现在这里。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            } else Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                latest.forEach { result ->
                    StudioCard(Modifier.width(244.dp).clickable(enabled = vm.connected && !vm.working) { vm.previewFile(result.getString("file")) }) {
                        AssetImage(vm, result.optString("media"), "最近作品", Modifier.fillMaxWidth().height(156.dp))
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(if(result.optString("kind") == "video") "视频作品  ·  点击播放" else "图片作品  ·  点击预览", style = MaterialTheme.typography.labelLarge)
                            Text(result.optString("prompt").ifBlank { "未填写描述" }, maxLines = 2, overflow = TextOverflow.Ellipsis, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ActiveTaskCard(vm: StudioViewModel, task: JSONObject, count: Int) {
    StudioCard(Modifier.fillMaxWidth().clickable { vm.navigate("任务") }) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row {
                Text("正在创作", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Text("$count 个进行中", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(task.optString("targetName"), style = MaterialTheme.typography.bodyMedium)
            if(!task.isNull("progress")) {
                val progress=(task.optDouble("progress")/100).toFloat().coerceIn(0f,1f)
                LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
                Text("当前节点 ${task.optString("node")} · ${(progress*100).toInt()}%", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            } else {
                LinearProgressIndicator(Modifier.fillMaxWidth())
                Text(when(task.optString("status")) { "new", "queued" -> "等待队列执行"; "downloading" -> "正在保存作品"; "cancel_requested" -> "正在取消"; else -> "正在处理，等待下一次进度更新" }, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun CreationWorkspace(vm: StudioViewModel) {
    if(EmptyProject(vm)) return
    var tab by rememberSaveable { mutableStateOf("分镜") }
    LaunchedEffect(vm.page) { if(vm.page in listOf("角色","场景","分镜")) tab = vm.page }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.padding(horizontal = 20.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("创作", style = MaterialTheme.typography.headlineSmall)
                    Text(vm.project!!.optString("name"), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                TextButton(onClick = { vm.navigate("项目") }) { Text("项目") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedButton(onClick = { vm.openGeneration("image") }, enabled = vm.connected && !vm.working, modifier = Modifier.weight(1f).testTag("generate:image")) { StudioIcon("image", Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("生成图片") }
                OutlinedButton(onClick = { vm.openGeneration("video") }, enabled = vm.connected && !vm.working, modifier = Modifier.weight(1f).testTag("generate:video")) { StudioIcon("video", Modifier.size(18.dp)); Spacer(Modifier.width(6.dp)); Text("生成视频") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("角色" to "角色资产", "场景" to "场景资产", "分镜" to "分镜工作区").forEach { (id, label) ->
                    FilterChip(tab == id, { tab = id }, label = { Text(label, style = MaterialTheme.typography.labelMedium) }, modifier = Modifier.weight(1f).testTag("workspace:$id"))
                }
            }
        }
        Box(Modifier.weight(1f)) { when(tab) { "角色" -> AssetsScreen(vm,"characters"); "场景" -> AssetsScreen(vm,"scenes"); else -> ShotsScreen(vm) } }
    }
}
