package cn.xiyi.xystudio

import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.Assert.*
import org.junit.Test

/** Transport fixtures only: not evidence of generation or device acceptance. */
class LanApiTest {
    @Test fun privateAddressBoundary() {
        assertEquals("http://192.168.50.198:8765",LanApi.validateBase("192.168.50.198:8765"))
        assertEquals("http://10.0.0.2:8765",LanApi.validateBase("10.0.0.2"))
        listOf("https://192.168.1.2:8765","8.8.8.8:8765","0.0.0.0","192.168.1.2.evil.example","http://user@192.168.1.2","http://192.168.1.2/path","http://192.168.1.2:99999","172.32.0.1").forEach {
            try { LanApi.validateBase(it);fail("accepted $it") } catch(_:IllegalArgumentException) { }
        }
    }
    @Test fun bearerEnvelopeAndSeedPrecision() {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setBody("{\"ok\":true,\"result\":\"job-test\"}"))
            val api=LanApi();api.base=server.url("/").toString().trimEnd('/');api.token="test-session"
            val generation=obj("seed" to "9223372036854775806","mode" to "qwen")
            val result=api.rpc("generation.submit",obj("generation" to generation),"project-test",7,"stable-request-id")
            assertEquals("job-test",result.getString("result"))
            val request=server.takeRequest()
            assertEquals("Bearer test-session",request.getHeader("Authorization"))
            val body=org.json.JSONObject(request.body.readUtf8())
            assertEquals("project-test",body.getString("projectId"));assertEquals(7,body.getInt("revision"))
            assertEquals("9223372036854775806",body.getJSONObject("payload").getJSONObject("generation").getString("seed"))
            assertFalse(request.path!!.contains("test-session"))
        }
    }
    @Test fun unauthorizedDoesNotBecomeSuccess() {
        MockWebServer().use { server ->
            server.enqueue(MockResponse().setResponseCode(401).setBody("{\"error\":\"revoked\"}"))
            val api=LanApi();api.base=server.url("/").toString().trimEnd('/')
            try { api.rpc("bootstrap",obj(),null,0);fail("expected rejection") }
            catch(e:AuthorizationException) { assertEquals("revoked",e.message) }
        }
    }
    @Test fun mediaNeverAcceptsArbitraryRemoteURL() {
        val api=LanApi();api.base="http://192.168.1.2:8765"
        assertEquals("",api.media("file:///C:/secret"))
        assertEquals("",api.media("https://example.com/steal"))
        assertEquals("http://192.168.1.2:8765/media/id?sig=signed",api.media("/media/id?sig=signed"))
    }
}
