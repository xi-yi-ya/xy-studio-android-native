package cn.xiyi.xystudio

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.After
import org.junit.runner.RunWith
import java.io.File

/** Actual app + real PC LAN backend. Enqueues ONLY into a verified paused QA queue.
 * No API responses, generated files, progress or successful cloud tasks are mocked.
 * Existing project video playback is distinct from paid Pixstag generation.
 */
@RunWith(AndroidJUnit4::class)
class PixstagDeviceTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()
    private fun waitText(text:String)=ui.waitUntil(30000){ui.onAllNodes(hasText(text,substring=true)).fetchSemanticsNodes().isNotEmpty()}
    private fun screenshot(name:String) {
        ui.waitForIdle()
        val folder=File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null),"pixstag-qa").apply{mkdirs()}
        check(UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).takeScreenshot(File(folder,"$name.png")))
    }
    @After fun captureFinalUiForDiagnostics() {
        val folder=File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null),"pixstag-qa").apply{mkdirs()}
        val device=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
        device.takeScreenshot(File(folder,"last-test-state.png"))
        device.dumpWindowHierarchy(File(folder,"last-test-state.xml"))
    }
    @Test fun nativeCloudFormReferencesPausedQueueAndExistingVideoPlayback() {
        val args=InstrumentationRegistry.getArguments()
        val base=args.getString("base") ?: ""
        val code=args.getString("code") ?: ""
        assumeTrue(base.isNotBlank()&&code.isNotBlank())
        val probe=LanApi().apply{pair(base,code,"Pixstag emulator verification")}
        fun snapshot()=probe.rpc("bootstrap",obj(),null,0).getJSONObject("result")
        val original=snapshot().getJSONObject("project")
        check(original.optBoolean("paused")){"QA queue must be paused: no paid submission is authorized"}
        val before=original.rows("tasks").map{it.getString("id")}.toSet()
        if(ui.onAllNodes(hasText("PC 服务地址")).fetchSemanticsNodes().isNotEmpty()) {
            ui.onNodeWithText("PC 服务地址").performTextReplacement(base)
            ui.onNodeWithText("连接密码（仅首次输入）").performTextReplacement(code)
            ui.onNodeWithText("连接并记住设备").performScrollTo().performClick()
        }
        waitText("PC 已连接")
        ui.onNodeWithTag("nav:创作").performClick()
        ui.onNodeWithTag("generate:video").performClick()
        waitText("制作视频")
        waitText("生成来源")
        if(ui.onAllNodes(hasText("本地 ComfyUI")).fetchSemanticsNodes().isNotEmpty()) {
            ui.onNodeWithText("本地 ComfyUI",substring=false).performClick()
            ui.onNodeWithText("Pixstag 云端 API",substring=false).performClick()
        }
        waitText("Pixstag 模型")
        ui.onNodeWithText("MiniMax-H3",substring=false).performClick()
        ui.onNodeWithText("doubao-seedance-2-5",substring=false).performClick()
        ui.onNodeWithText("提示词",substring=false).performScrollTo().performTextReplacement("海边的白色灯塔，镜头缓慢靠近，海浪自然起伏。界面验收，不付费提交。")
        ui.onNodeWithText("视频秒数",substring=false).performScrollTo().performTextReplacement("3")
        ui.onNodeWithTag("reviewGeneration").performClick()
        waitText("4–30 的整数秒")
        ui.onNodeWithText("视频秒数",substring=false).performScrollTo().performTextReplacement("5")
        ui.onNodeWithTag("reviewGeneration").performClick()
        waitText("确认生成视频")
        waitText("可能消耗账户积分")
        screenshot("01-cloud-text-confirmation")
        assertEquals(before,snapshot().getJSONObject("project").rows("tasks").map{it.getString("id")}.toSet())
        ui.onNodeWithText("返回修改").performClick()
        ui.onNodeWithText("Pixstag 文生视频",substring=false).performScrollTo().performClick()
        ui.onNodeWithText("Pixstag 多模态参考视频",substring=false).performClick()
        ui.onNodeWithTag("chooseReferences").performScrollTo().performClick()
        waitText("选择项目图片")
        ui.onAllNodes(hasTestTag("finishReferences")).onFirst().assertExists()
        val refs=probe.rpc("library.query",obj("kind" to "image","limit" to 1),original.getString("id"),0).getJSONObject("result").rows("items")
        ui.onNodeWithTag("reference:${refs.first().getString("file")}").performClick()
        ui.onNodeWithTag("finishReferences").performClick()
        ui.onNodeWithTag("chooseVideoReferences").performScrollTo().performClick()
        waitText("选择项目视频")
        val videos=probe.rpc("library.query",obj("kind" to "video","limit" to 1),original.getString("id"),0).getJSONObject("result").rows("items")
        ui.onNodeWithTag("reference:${videos.first().getString("file")}").performClick()
        ui.onNodeWithTag("finishReferences").performClick()
        ui.onNodeWithTag("reviewGeneration").performClick()
        waitText("参考图片 1 张 · 视频 1 个")
        screenshot("02-multimodal-confirmation")
        // Verify the queue remains paused immediately before the confirm action.
        check(snapshot().getJSONObject("project").optBoolean("paused"))
        ui.onNodeWithTag("submitGeneration").performClick()
        waitText("任务与生成历史")
        ui.waitUntil(30000){snapshot().getJSONObject("project").rows("tasks").any{it.getString("id") !in before}}
        val created=snapshot().getJSONObject("project").rows("tasks").single{it.getString("id") !in before}
        assertEquals("new",created.getString("status"));assertTrue(created.isNull("remoteId"));assertEquals("video",created.getString("kind"))
        assertEquals("pixstag",created.getString("provider"));assertTrue(created.isNull("progress"))
        screenshot("03-real-paused-queue-not-submitted")
        ui.onNodeWithText("取消任务",substring=false).performScrollTo().performClick()
        ui.onNodeWithText("确认取消",substring=false).performClick()
        ui.waitUntil(30000){snapshot().getJSONObject("project").rows("tasks").single{it.getString("id")==created.getString("id")}.optString("status")=="cancelled"}
        ui.onNodeWithTag("nav:素材").performClick()
        ui.onNodeWithText("视频库",substring=false).performClick()
        waitText("点击播放视频")
        ui.onAllNodes(hasText("点击播放视频")).onFirst().performClick()
        waitText("视频预览")
        ui.onNodeWithText("播放 / 暂停",substring=false).performClick()
        ui.waitUntil(30000){ui.onAllNodes(hasText("已播放",substring=true)).fetchSemanticsNodes().any{n->n.config[androidx.compose.ui.semantics.SemanticsProperties.Text].any{(Regex("已播放 ([0-9.]+) 秒").find(it.text)?.groupValues?.get(1)?.toDoubleOrNull()?:0.0)>=1.0}}}
        screenshot("04-existing-project-video-playback")
        ui.onNodeWithText("关闭",substring=false).performClick()
        ui.onNodeWithTag("nav:创作").performClick()
        ui.onNodeWithTag("generate:video").performClick()
        waitText("Pixstag 云端 API")
        ui.onNodeWithText("Pixstag 云端 API",substring=false).performClick()
        ui.onNodeWithText("本地 ComfyUI",substring=false).performClick()
        ui.onNodeWithText("采样步数 (0 自动)",substring=false).performScrollTo().assertExists()
        screenshot("05-local-workflow-still-available")
        ui.onNodeWithText("关闭",substring=false).performClick()
        ui.onNodeWithText("放弃并关闭",substring=false).performClick()
        check(snapshot().getJSONObject("project").rows("tasks").none{!it.isNull("remoteId")&&it.getString("id") !in before}){"Unexpected remote submission"}
    }
}
