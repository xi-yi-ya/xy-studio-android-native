package cn.xiyi.xystudio

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

@Composable fun LibraryFilters(vm:StudioViewModel) {
    var open by remember { mutableStateOf(false) }
    Row(verticalAlignment=Alignment.CenterVertically) {
        TextButton(onClick={open=true}){Text("筛选与排序")}
        FilterChip(vm.libraryTrash,{vm.libraryTrash=!vm.libraryTrash;vm.searchLibrary()},label={Text("回收站")},enabled=!vm.working)
    }
    if(open) {
        var source by remember { mutableStateOf(vm.librarySource) }
        var owner by remember { mutableStateOf(vm.libraryOwner) }
        var sort by remember { mutableStateOf(vm.librarySort) }
        AlertDialog(onDismissRequest={open=false},title={Text("素材筛选")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(12.dp)) {
            Choice("来源",source,listOf("all" to "全部来源","generated" to "生成结果","imported" to "导入素材","project" to "项目素材")){source=it}
            Choice("关联",owner,listOf("all" to "全部关联","characters" to "角色","scenes" to "场景","shots" to "分镜","unassigned" to "未关联","deleted" to "已删除条目的素材")){owner=it}
            Choice("排序",sort,listOf("newest" to "最新优先","oldest" to "最早优先","name" to "按名称")){sort=it}
        }},confirmButton={TextButton(onClick={vm.librarySource=source;vm.libraryOwner=owner;vm.librarySort=sort;vm.searchLibrary();open=false},enabled=!vm.working){Text("应用筛选")}},dismissButton={TextButton(onClick={source="all";owner="all";sort="newest"}){Text("重置条件")}})
    }
}
