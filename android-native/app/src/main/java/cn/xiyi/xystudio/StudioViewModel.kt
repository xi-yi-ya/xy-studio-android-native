package cn.xiyi.xystudio

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import androidx.compose.runtime.*
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import okhttp3.*
import org.json.JSONArray
import org.json.JSONObject

class StudioViewModel(app: Application): AndroidViewModel(app) {
    val api = LanApi()
    private val prefs = app.getSharedPreferences("lan-address",0)
    var address by mutableStateOf(prefs.getString("address", "") ?: "")
    var state by mutableStateOf(JSONObject()); private set
    var connected by mutableStateOf(false); private set
    var status by mutableStateOf("未连接 PC"); private set
    var error by mutableStateOf("")
    var working by mutableStateOf(false); private set
    var page by mutableStateOf("首页")
    var assistantReturnPage by mutableStateOf("创作"); private set
    var chatDraft by mutableStateOf("")
    var libraryKind by mutableStateOf("image")
    var librarySource by mutableStateOf("all")
    var libraryOwner by mutableStateOf("all")
    var librarySort by mutableStateOf("newest")
    var libraryTrash by mutableStateOf(false)
    var library by mutableStateOf<List<JSONObject>>(emptyList()); private set
    var libraryTotal by mutableIntStateOf(0); private set
    var libraryOffset by mutableIntStateOf(0); private set
    var search by mutableStateOf("")
    var preview by mutableStateOf<JSONObject?>(null)
    var generation by mutableStateOf<JSONObject?>(null)
    var generationReviewId by mutableStateOf<String?>(null)
    var generationTarget by mutableStateOf<String?>(null)
    var submissionCount by mutableIntStateOf(0); private set
    var references by mutableStateOf<List<JSONObject>>(emptyList()); private set
    private val commands = Mutex()
    private var ws: WebSocket? = null
    private var reconnectJob: Job? = null
    private var libraryJob: Job? = null
    private var connectionEpoch = 0
    private var delayMs = 1000L
    private var lastProjectStamp = ""
    val project: JSONObject? get() = state.optJSONObject("project")
    val revision: Int get() = state.optInt("lanRevision")
    val review: JSONObject? get() = state.optJSONObject("review")
    var hasAuthorization by mutableStateOf(false); private set
    private val connectionStore=ConnectionStore(app)
    var remembered by mutableStateOf(connectionStore.load()!=null); private set
    init { connectionStore.load()?.let { address=it.getString("base");pair(it.getString("password"),it.optString("name","我的 Android")) } }

    fun action(block: suspend () -> Unit) {
        if(working) return
        working = true; error = ""
        viewModelScope.launch {
            try { block() }
            catch (e: CancellationException) { throw e }
            catch (e: Exception) { fail(e) }
            finally { working = false }
        }
    }
    private fun fail(e: Exception) {
        error = if(e is java.io.IOException) "连接中断或超时。操作可能已执行，请重连后检查任务历史，勿直接重复提交。" else e.message ?: e.toString()
        if(e is AuthorizationException) disconnect(clearState = false)
        if(e is java.io.IOException) { connected = false; status = "连接中断" }
    }
    private fun receive(next: JSONObject) {
        val oldId = project?.optString("id")
        state = next
        if(project?.optString("id") != oldId) {
            library = emptyList(); libraryOffset = 0; preview = null; generation = null; references = emptyList()
        }
        val stamp = project?.let { it.optString("id")+it.optString("updated") } ?: ""
        if(stamp != lastProjectStamp) {
            lastProjectStamp = stamp
            if(page == "素材") scheduleLibrary()
        }
    }
    suspend fun call(command: String, payload: JSONObject = JSONObject(), expectedRevision: Int = revision): Any? = commands.withLock {
        val id = project?.optString("id")
        val response = withContext(Dispatchers.IO) { api.rpc(command,payload,id,expectedRevision) }
        response.optJSONObject("state")?.let { receive(it) }
        check(response.optBoolean("ok")) { response.optString("error","操作失败") }
        response.opt("result")
    }
    fun pair(code: String, name: String) = action {
        disconnect(forget=false)
        withContext(Dispatchers.IO) { api.pair(address,code,name) }
        hasAuthorization=true
        address = api.base; prefs.edit().putString("address",address).apply()
        connectionStore.save(address,code,name);remembered=true
        receive(call("bootstrap") as JSONObject)
        startSocket()
    }
    fun reconnect() = action {
        if(!hasAuthorization) {
            val saved=connectionStore.load() ?: error("请先输入 PC 连接密码")
            withContext(Dispatchers.IO){api.pair(saved.getString("base"),saved.getString("password"),saved.optString("name","我的 Android"))}
            hasAuthorization=true
        }
        receive(call("bootstrap") as JSONObject)
        startSocket()
    }
    fun disconnect(clearState: Boolean = true, forget:Boolean=true) {
        connectionEpoch++; reconnectJob?.cancel(); ws?.cancel(); ws = null
        api.token = ""; hasAuthorization=false; connected = false; status = "未连接 PC"
        if(forget){connectionStore.clear();remembered=false}
        if(clearState) { state=JSONObject(); library=emptyList(); preview=null; generation=null }
    }
    private fun startSocket() {
        val epoch = ++connectionEpoch
        reconnectJob?.cancel(); ws?.cancel()
        status = "正在连接状态同步"
        ws = api.client.newWebSocket(Request.Builder().url(api.base.replace("http:","ws:")+"/events").build(),object: WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) { webSocket.send(obj("token" to api.token).toString()) }
            override fun onMessage(webSocket: WebSocket, text: String) {
                viewModelScope.launch {
                    if(epoch != connectionEpoch) return@launch
                    try {
                        val message=JSONObject(text)
                        if(message.optString("type")=="state") {
                            receive(message.getJSONObject("state")); connected=true; status="已连接 PC · 实时同步"; delayMs=1000
                        }
                    } catch(e:Exception) { fail(e) }
                }
            }
            override fun onFailure(webSocket: WebSocket,t:Throwable,response:Response?) { lost(epoch,0) }
            override fun onClosed(webSocket: WebSocket,code:Int,reason:String) { lost(epoch,code) }
            override fun onClosing(webSocket: WebSocket,code:Int,reason:String) { webSocket.close(code,reason) }
        })
    }
    private fun lost(epoch:Int,code:Int) {
        viewModelScope.launch {
            if(epoch != connectionEpoch) return@launch
            connected=false
            if(code==4001) { disconnect(false,forget=false);reconnect();return@launch }
            status="连接中断，正在重连"
            reconnectJob?.cancel()
            reconnectJob=viewModelScope.launch { delay(delayMs); delayMs=(delayMs*2).coerceAtMost(10000); if(hasAuthorization)startSocket() }
        }
    }
    fun refresh() = action { call("bootstrap"); if(page=="素材")loadLibrary() }
    fun navigate(next:String) {
        if(next=="AI" && page!="AI")assistantReturnPage=page
        page=next
        if(next=="素材")scheduleLibrary()
    }
    private fun scheduleLibrary() {
        libraryJob?.cancel()
        libraryJob=viewModelScope.launch { delay(400);try{loadLibrary()}catch(e:CancellationException){throw e}catch(e:Exception){fail(e)} }
    }
    suspend fun loadLibrary(offset:Int=libraryOffset) {
        if(project==null)return
        val result=call("library.query",obj("kind" to libraryKind,"query" to search,"offset" to offset,"limit" to 40,"source" to librarySource,"owner" to libraryOwner,"sort" to librarySort,"trash" to libraryTrash)) as JSONObject
        library=result.rows("items");libraryTotal=result.optInt("total");libraryOffset=offset
    }
    fun searchLibrary(kind:String=libraryKind,offset:Int=0) = action { libraryKind=kind;loadLibrary(offset) }
    fun previewFile(file:String) = action { preview=call("library.preview",obj("file" to file)) as JSONObject }
    fun openGeneration(kind:String,previous:JSONObject?=null,reviewId:String?=null,reference:String?=null,target:String?=null) = action {
        val args=obj("kind" to kind)
        if(target!=null)args.put("target",target)
        if(reference!=null) args.put("mode",if(kind=="video")"h3_i2v" else "qwen_edit")
        val g=previous?.copyJson() ?: call("generation.defaults",args) as JSONObject
        if(reference!=null)g.put("references",JSONArray(listOf(reference)))
        val records=mutableListOf<JSONObject>()
        var more=true
        while(more) {
            val r=call("library.query",obj("kind" to "image","limit" to 100,"offset" to records.size)) as JSONObject
            records.addAll(r.rows("items"));more=r.optBoolean("hasMore")
        }
        references=records; preview=null; generation=g; generationReviewId=reviewId;generationTarget=target
    }
    fun submitGeneration(value:JSONObject) = action {
        if(generationReviewId!=null)call("review.respond",obj("id" to generationReviewId,"accepted" to true,"generation" to value))
        else call("generation.submit",obj("generation" to value,"target" to generationTarget))
        generation=null;generationReviewId=null;generationTarget=null;submissionCount++;page="任务"
    }
    fun command(name:String,payload:JSONObject=JSONObject(),expectedRevision:Int=revision) = action { call(name,payload,expectedRevision) }
    fun importMedia(uri:Uri,kind:String=libraryKind,attachToChat:Boolean=false) = action {
        val id=project?.getString("id") ?: error("请先打开项目")
        val response=withContext(Dispatchers.IO) {
            val resolver=getApplication<Application>().contentResolver
            val filename=resolver.query(uri,null,null,null,null)?.use { c ->
                if(c.moveToFirst())c.getString(c.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME)) else null
            } ?: uri.lastPathSegment ?: "phone.png"
            val bytes=resolver.openInputStream(uri)?.use { input ->
                val output=java.io.ByteArrayOutputStream()
                val buffer=ByteArray(64*1024)
                while(true) {
                    val n=input.read(buffer);if(n<0)break
                    require(output.size()+n<=100*1024*1024){"单个素材最多 100 MB"}
                    output.write(buffer,0,n)
                }
                output.toByteArray()
            } ?: error("无法读取素材")
            api.upload(id,filename,bytes,kind)
        }
        check(project?.optString("id")==id){"项目已切换，素材已保存到原项目，请返回原项目查看。"}
        if(attachToChat)response.strings("result").forEach { file -> call("context.add_media",obj("file" to file)) }
        if(page=="素材")loadLibrary(0)
    }
    override fun onCleared() { connectionEpoch++; ws?.cancel(); api.client.dispatcher.executorService.shutdown();super.onCleared() }
}
