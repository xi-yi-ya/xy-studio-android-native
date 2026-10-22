package cn.xiyi.xystudio

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import org.json.JSONObject
import org.json.JSONArray

/** Opt-in device/emulator test against a real PC. No HTTP stubs or UI fixtures.
 * Supply base/code instrumentation arguments. Optional generate=true consumes GPU.
 */
@RunWith(AndroidJUnit4::class)
class RealLanSmokeTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()
    private fun waitText(text:String,timeout:Long=30000) {
        ui.waitUntil(timeout) { ui.onAllNodes(hasText(text,substring=true)).fetchSemanticsNodes().isNotEmpty() }
    }
    private fun screenshot(name:String) {
        ui.waitForIdle()
        // Native window animations can outlive Compose semantics becoming available.
        Thread.sleep(400)
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val folder=File(context.getExternalFilesDir(null),"qa").apply{mkdirs()}
        check(UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).takeScreenshot(File(folder,"$name.png")))
    }
    // Read-only verification over the real LAN; generation is submitted only by UI clicks.
    private val probe=LanApi()
    private fun snapshot()=probe.rpc("bootstrap",obj(),null,0).getJSONObject("result")
    private fun taskIds()=snapshot().getJSONObject("project").rows("tasks").map{it.getString("id")}.toSet()
    private fun waitNewTask(before:Set<String>,kind:String):JSONObject {
        val records=JSONArray()
        var latest:JSONObject?=null
        var last=""
        try {
            ui.waitUntil(1200000) {
                latest=snapshot().getJSONObject("project").rows("tasks").lastOrNull{it.getString("id") !in before&&it.optString("kind")==kind}
                latest?.let {
                    val status=it.optString("status")
                    val key=status+it.optString("node")+it.optString("progress")
                    if(key!=last){last=key;records.put(it)}
                    check(status !in listOf("failed","cancelled","unknown","detached")){"Real $kind task failed: $it"}
                    status=="completed"&&it.rows("results").isNotEmpty()
                } ?: false
            }
        } finally {
            val context=InstrumentationRegistry.getInstrumentation().targetContext
            File(context.getExternalFilesDir(null),"qa/$kind-task-states.json").writeText(records.toString(2))
        }
        return checkNotNull(latest)
    }
    @Test fun nativeAppRealPcProjectGenerationAndPlayback() {
        val args=InstrumentationRegistry.getArguments()
        val base=args.getString("base") ?: ""
        val code=args.getString("code") ?: ""
        assumeTrue("Requires explicitly supplied live PC and connection password",base.isNotBlank()&&code.isNotBlank())
        probe.pair(base,code,"native read-only verification")
        if(args.getString("reuseOnly")=="true") {
            waitText("PC 已连接",60000)
        }
        if(args.getString("reuseOnly")!="true" && ui.onAllNodes(hasText("连接密码（仅首次输入）")).fetchSemanticsNodes().isNotEmpty()) {
            ui.onNodeWithText("PC 服务地址").performTextReplacement(base)
            ui.onNodeWithText("连接密码（仅首次输入）").performTextInput(code)
            ui.onNodeWithText("连接并记住设备").performScrollTo().performClick()
        }
        waitText("PC 已连接")
        screenshot("01-native-connected-projects")
        ui.onNodeWithText("素材",useUnmergedTree=true).performScrollTo().performClick()
        waitText("素材库")
        ui.waitUntil(30000){ui.onAllNodes(hasText("点击放大图片")).fetchSemanticsNodes().isNotEmpty()}
        screenshot("02-native-real-images")
        if(args.getString("generate")=="true") {
            val resumeImage=args.getString("imageJob")
            val newImage=if(resumeImage==null) {
            val beforeImage=taskIds()
            ui.onNodeWithTag("nav:首页").performClick()
            ui.onNodeWithText("生成图片").performClick()
            waitText("创作图片")
            // Blank prompt is rejected locally and cannot create a PC task.
            ui.onNodeWithText("提示词").performTextReplacement("")
            ui.onNodeWithTag("reviewGeneration").performClick()
            waitText("请填写提示词")
            check(taskIds()==beforeImage){"Validation unexpectedly created a task"}
            ui.onNodeWithText("提示词").performTextReplacement("A small friendly orange toy robot on a clean pale blue studio table, soft daylight, clear silhouette, miniature product photography, no text.")
            ui.onNodeWithText("像素量 MP").performScrollTo().performTextReplacement("0.2")
            ui.onNodeWithText("采样步数 (0 自动)").performTextReplacement("4")
            screenshot("03-native-generation-review")
            ui.onNodeWithTag("reviewGeneration").performClick()
            waitText("确认生成图片")
            check(taskIds()==beforeImage){"Preflight unexpectedly created a task"}
            ui.onNodeWithText("返回修改").performClick()
            ui.onNodeWithText("提示词").performScrollTo().assertTextContains("A small friendly",substring=true)
            ui.onNodeWithTag("reviewGeneration").performClick()
            waitText("确认生成图片")
            screenshot("03b-native-image-confirmation")
            ui.onNodeWithText("确认并加入 PC 队列").performClick()
            waitText("任务与生成历史")
            waitText("正在生成",120000)
            screenshot("04-native-real-image-progress")
            waitNewTask(beforeImage,"image")
            } else snapshot().getJSONObject("project").rows("tasks").first{it.getString("id")==resumeImage&&it.optString("status")=="completed"&&it.optString("kind")=="image"}
            val beforeVideo=taskIds()
            val newFile=newImage.rows("results").first().getString("file")
            ui.onNodeWithText("任务",useUnmergedTree=true).performScrollTo().performClick()
            ui.waitUntil(30000) { ui.onAllNodes(hasTestTag("imageToVideo:$newFile")).fetchSemanticsNodes().isNotEmpty() }
            ui.onNodeWithTag("imageToVideo:$newFile").performScrollTo().performClick()
            waitText("制作视频")
            waitText("选择参考图片 · 1/1")
            ui.onNodeWithText("提示词").performTextReplacement("The orange toy robot gently waves an arm. A slow camera push in, stable composition, soft studio daylight. Quiet room tone, no speech, no music.")
            ui.onNodeWithText("像素量 MP").performScrollTo().performTextReplacement("0.1")
            ui.onNodeWithText("采样步数 (0 自动)").performTextReplacement("4")
            ui.onNodeWithText("视频秒数").performScrollTo().performTextReplacement("2")
            while(ui.onAllNodes(hasText("移除")).fetchSemanticsNodes().isNotEmpty())ui.onAllNodes(hasText("移除")).onFirst().performScrollTo().performClick()
            ui.onNodeWithTag("chooseReferences").performScrollTo().performClick()
            val s=snapshot()
            val referenceName=probe.rpc("library.query",obj("kind" to "image","limit" to 100),s.getJSONObject("project").getString("id"),s.optInt("lanRevision")).getJSONObject("result").rows("items").first{it.optString("file")==newFile}.getString("name")
            ui.onNodeWithText("搜索参考图片").performTextReplacement(referenceName)
            ui.onNodeWithTag("reference:$newFile").performScrollTo().performClick()
            ui.onNodeWithTag("finishReferences").performClick()
            ui.onNodeWithTag("reviewGeneration").performClick()
            waitText("确认生成视频")
            screenshot("05a-native-video-confirmation")
            ui.onNodeWithText("确认并加入 PC 队列").performClick()
            waitText("正在生成",180000)
            screenshot("05-native-real-video-progress")
            waitNewTask(beforeVideo,"video")
        }
        ui.onNodeWithText("素材",useUnmergedTree=true).performScrollTo().performClick()
        ui.onNodeWithText("视频库").performClick()
        waitText("点击播放视频")
        screenshot("06-native-real-video-library")
        ui.onAllNodes(hasText("点击播放视频")).onFirst().performClick()
        // Image itself opens preview. Its content description is the asset name;
        // click the card's top image using its shared parent if label isn't clickable.
        if(ui.onAllNodes(hasText("视频预览")).fetchSemanticsNodes().isEmpty()) {
            ui.onAllNodes(hasText("点击播放视频")).onFirst().onParent().onParent().onChildren().onFirst().performClick()
        }
        waitText("视频预览")
        ui.onNodeWithText("播放 / 暂停").performClick()
        ui.waitUntil(60000) { ui.onAllNodes(hasText("已播放",substring=true)).fetchSemanticsNodes().any { node ->
            val texts=node.config[androidx.compose.ui.semantics.SemanticsProperties.Text]
            texts.any { (Regex("已播放 ([0-9.]+) 秒").find(it.text)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0)>=1.0 }
        } }
        screenshot("07-native-media3-video-playback")
    }
}
