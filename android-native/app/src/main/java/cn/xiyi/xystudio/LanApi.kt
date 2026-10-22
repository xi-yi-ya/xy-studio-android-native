package cn.xiyi.xystudio

import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI
import java.net.Proxy
import java.util.UUID
import java.util.concurrent.TimeUnit

fun obj(vararg values: Pair<String, Any?>) = JSONObject().apply { values.forEach { (k,v) -> put(k,v ?: JSONObject.NULL) } }
fun JSONObject.rows(key: String): List<JSONObject> = optJSONArray(key)?.let { a -> (0 until a.length()).mapNotNull { a.optJSONObject(it) } } ?: emptyList()
fun JSONObject.strings(key: String): List<String> = optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()
fun JSONObject.copyJson() = JSONObject(toString())

/** Only credentials for Studio LAN are held here. No DeepSeek key or workflows. */
class LanApi {
    val client = OkHttpClient.Builder().proxy(Proxy.NO_PROXY)
        .connectTimeout(8, TimeUnit.SECONDS).readTimeout(45, TimeUnit.SECONDS)
        .callTimeout(60, TimeUnit.SECONDS).pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(false).followRedirects(false).build()
    @Volatile var base = ""
    @Volatile var token = ""

    companion object {
        fun validateBase(input: String): String {
            val uri = URI(if (input.contains("://")) input.trim() else "http://${input.trim()}")
            val p = uri.host?.split('.')?.map { it.toIntOrNull() ?: -1 } ?: emptyList()
            val local = p.size == 4 && p.all { it in 0..255 } &&
                (p[0] == 10 || p[0] == 127 || (p[0] == 192 && p[1] == 168) || (p[0] == 172 && p[1] in 16..31))
            require(local && uri.scheme == "http" && uri.userInfo == null && uri.query == null && uri.fragment == null &&
                (uri.path.isNullOrEmpty() || uri.path == "/") && (uri.port == -1 || uri.port in 1..65535)) {
                "请输入 PC 局域网 IPv4 与端口，例如 http://192.168.50.198:8765"
            }
            return "http://${uri.host}:${if(uri.port == -1) 8765 else uri.port}"
        }
    }

    fun request(path: String, body: RequestBody): JSONObject {
        val builder = Request.Builder().url(base + path).post(body)
        if (token.isNotEmpty()) builder.header("Authorization", "Bearer $token")
        client.newCall(builder.build()).execute().use { response ->
            val result = JSONObject(response.body?.string() ?: "{}")
            if (response.code == 401) throw AuthorizationException(result.optString("error", "设备授权失效，请重新配对"))
            check(response.isSuccessful) { result.optString("error", "PC 服务 HTTP ${response.code}") }
            return result
        }
    }
    fun json(path: String, value: JSONObject) = request(path,value.toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
    fun pair(address: String, code: String, name: String) {
        base = validateBase(address)
        token = ""
        token = json("/pair",obj("code" to code,"name" to name)).getString("token")
    }
    fun rpc(command: String, payload: JSONObject, projectId: String?, revision: Int, id: String = UUID.randomUUID().toString()): JSONObject =
        json("/rpc",obj("id" to id,"command" to command,"payload" to payload,"projectId" to projectId,"revision" to revision))

    fun upload(projectId: String, filename: String, bytes: ByteArray, kind: String): JSONObject {
        require(bytes.size <= 100*1024*1024) { "单个素材最多 100 MB" }
        val metadata = obj("projectId" to projectId,"command" to "library.import","payload" to obj("kind" to kind))
        val multipart = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("metadata",metadata.toString())
            .addFormDataPart("file",filename,bytes.toRequestBody("application/octet-stream".toMediaType())).build()
        return request("/upload",multipart)
    }
    fun media(value: String): String = if(value.startsWith("/media/")) base + value else ""
}
class AuthorizationException(message: String): Exception(message)
