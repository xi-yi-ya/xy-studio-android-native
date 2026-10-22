package cn.xiyi.xystudio

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.junit.Rule
import org.junit.Test
import org.junit.Assume.assumeTrue
import org.junit.runner.RunWith
import java.io.File

/** Real device + real project navigation. Does not submit generation or send AI messages. */
@RunWith(AndroidJUnit4::class)
class NativeNavigationTest {
    @get:Rule val ui = createAndroidComposeRule<MainActivity>()
    private fun waitText(text: String) = ui.waitUntil(30000) { ui.onAllNodes(hasText(text,substring=true)).fetchSemanticsNodes().isNotEmpty() }
    private fun screenshot(name: String) {
        ui.waitForIdle();Thread.sleep(400)
        val folder=File(InstrumentationRegistry.getInstrumentation().targetContext.getExternalFilesDir(null),"design-qa").apply{mkdirs()}
        check(UiDevice.getInstance(InstrumentationRegistry.getInstrumentation()).takeScreenshot(File(folder,"$name.png")))
    }
    @Test fun realProjectHomeCreationLibraryTasksAndFullscreenAssistant() {
        val args=InstrumentationRegistry.getArguments()
        val base=args.getString("base") ?: ""
        val code=args.getString("code") ?: ""
        assumeTrue(base.isNotBlank() && code.isNotBlank())
        val probe=LanApi().apply{pair(base,code,"navigation read-only verification")}
        fun snapshot()=probe.rpc("bootstrap",obj(),null,0).getJSONObject("result")
        val project=snapshot().getJSONObject("project")
        val before=project.rows("tasks").map{it.getString("id")}.toSet()
        waitText("PC 已连接")
        ui.onNodeWithTag("nav:首页").performClick()
        waitText("创作工作台")
        ui.onNodeWithText(project.getString("name")).assertExists()
        listOf("首页","创作","素材","任务").forEach { ui.onNodeWithTag("nav:$it").assertIsDisplayed() }
        screenshot("01-home")
        ui.onNodeWithTag("homeContent").performScrollToNode(hasText("最近作品"))
        screenshot("02-recent-works")
        ui.onNodeWithTag("nav:创作").performClick()
        ui.onNodeWithTag("workspace:角色").performClick()
        screenshot("03-creation-characters")
        ui.onNodeWithTag("workspace:场景").performClick()
        ui.onNodeWithTag("workspace:分镜").performClick()
        waitText("故事")
        screenshot("04-storyboard")
        ui.onNodeWithTag("openAssistant").performClick()
        waitText("AI 创作助手")
        ui.onNodeWithTag("nav:首页").assertDoesNotExist()
        screenshot("05-fullscreen-assistant")
        ui.onNodeWithText("对话设置").performClick()
        waitText("DeepSeek 模型")
        ui.onNodeWithText("收起设置").performClick()
        ui.onNodeWithText("和 AI 讨论当前项目").performTextInput("临时界面测试草稿，不发送")
        screenshot("05b-assistant-keyboard")
        ui.onNodeWithTag("backToWorkspace").performClick()
        ui.onNodeWithTag("nav:创作").assertIsDisplayed()
        ui.onNodeWithTag("openAssistant").performClick()
        ui.onNodeWithText("和 AI 讨论当前项目").assertTextContains("临时界面测试草稿，不发送")
        ui.onNodeWithText("和 AI 讨论当前项目").performTextReplacement("")
        ui.onNodeWithTag("backToWorkspace").performClick()
        ui.onNodeWithTag("generate:image").performClick()
        waitText("创作图片")
        screenshot("06-image-form")
        ui.onNodeWithText("关闭").performClick()
        waitText("离开生成编辑？")
        ui.onNodeWithText("继续编辑").performClick()
        waitText("创作图片")
        ui.onNodeWithText("关闭").performClick()
        ui.onNodeWithText("放弃并关闭").performClick()
        ui.onNodeWithTag("generate:video").performClick()
        waitText("制作视频")
        screenshot("07-video-form")
        ui.onNodeWithText("关闭").performClick()
        ui.onNodeWithText("放弃并关闭").performClick()
        ui.onNodeWithTag("nav:素材").performClick()
        waitText("点击放大图片")
        screenshot("08-image-library")
        ui.onNodeWithText("视频库").performClick()
        waitText("点击播放视频")
        screenshot("09-video-library")
        ui.onAllNodes(hasText("点击播放视频")).onFirst().performClick()
        waitText("视频预览")
        ui.onNodeWithText("播放 / 暂停").performClick()
        ui.waitUntil(30000) { ui.onAllNodes(hasText("已播放",substring=true)).fetchSemanticsNodes().any { n ->
            n.config[androidx.compose.ui.semantics.SemanticsProperties.Text].any { (Regex("已播放 ([0-9.]+) 秒").find(it.text)?.groupValues?.get(1)?.toDoubleOrNull() ?: 0.0)>=1.0 }
        } }
        screenshot("10-video-playback")
        ui.onNodeWithText("关闭").performClick()
        ui.onNodeWithTag("nav:任务").performClick()
        waitText("任务与生成历史")
        screenshot("11-tasks")
        ui.onNodeWithTag("nav:首页").performClick()
        ui.onNodeWithTag("manageProjects").performScrollTo().performClick()
        waitText("你的创作空间")
        screenshot("12-projects")
        ui.onNodeWithTag("backToWorkspace").performClick()
        waitText("创作工作台")
        check(snapshot().getJSONObject("project").rows("tasks").map{it.getString("id")}.toSet()==before) { "Navigation unexpectedly created a task" }
    }
}
