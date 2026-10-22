package cn.xiyi.xystudio

import android.net.Uri
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import androidx.test.uiautomator.UiDevice
import org.json.JSONObject
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class ChatMediaDeviceTest {
    @get:Rule val ui=createAndroidComposeRule<MainActivity>()
    private val device get()=UiDevice.getInstance(InstrumentationRegistry.getInstrumentation())
    private fun waitText(text:String)=ui.waitUntil(30000){ui.onAllNodes(hasText(text,substring=true)).fetchSemanticsNodes().isNotEmpty()}
    private fun shot(name:String) {
        ui.waitForIdle();Thread.sleep(800)
        val folder=File(ui.activity.getExternalFilesDir(null),"chat-media-qa").apply{mkdirs()}
        check(device.takeScreenshot(File(folder,"$name.png")))
    }
    @Test fun attachRealImagesVideosImportAndWorkspaceActions() {
        val args=InstrumentationRegistry.getArguments();val base=args.getString("base") ?: "";val code=args.getString("code") ?: ""
        assumeTrue(base.isNotEmpty()&&code.isNotEmpty())
        val api=LanApi().apply{pair(base,code,"native attachment verification")}
        fun snapshot()=api.rpc("bootstrap",obj(),null,0).getJSONObject("result")
        fun rpc(command:String,payload:JSONObject=obj()):Any? {
            val s=snapshot();val response=api.rpc(command,payload,s.getJSONObject("project").getString("id"),s.getInt("lanRevision"))
            check(response.optBoolean("ok")){response.optString("error")};return response.opt("result")
        }
        val before=snapshot();val originalMedia=before.rows("mediaContext");val originalIds=before.strings("contextIds")
        val originalSelected=before.optString("selectedId").takeUnless{it.isBlank()||it=="null"}
        val project=before.getJSONObject("project");val jobs=project.rows("tasks").map{it.getString("id")}.toSet();val chats=project.rows("chat").size
        val image=(rpc("library.query",obj("kind" to "image","limit" to 1)) as JSONObject).rows("items").first()
        val video=(rpc("library.query",obj("kind" to "video","limit" to 1)) as JSONObject).rows("items").first()
        val vm=ViewModelProvider(ui.activity)[StudioViewModel::class.java]
        val imported=mutableListOf<String>()
        fun idle()=ui.waitUntil(30000){!vm.working}
        try {
            rpc("context.clear")
            waitText("PC 已连接")
            ui.onNodeWithTag("nav:创作").performClick();ui.onNodeWithTag("openAssistant").performClick();waitText("AI 创作助手")
            ui.onNodeWithTag("chatAddMedia").performClick();waitText("选择参考素材")
            ui.onNodeWithTag("pickMedia:${image.getString("file")}").performClick();idle()
            ui.waitUntil(10000){snapshot().rows("mediaContext").any{it.optString("file")==image.getString("file")}}
            ui.onNodeWithTag("pickKind:video").performClick()
            ui.waitUntil(20000){ui.onAllNodesWithTag("pickMedia:${video.getString("file")}").fetchSemanticsNodes().isNotEmpty()}
            ui.onNodeWithTag("pickMedia:${video.getString("file")}").performClick();idle();shot("01-picker-video")
            ui.onNodeWithTag("closeMediaPicker").performClick();waitText("下一条消息引用 2 份素材")
            shot("02-chat-attachments")
            ui.onNodeWithTag("chatAttachment:${image.getString("file")}").assertExists()
            ui.onNodeWithTag("removeAttachment:${image.getString("file")}").performClick();idle();waitText("下一条消息引用 1 份素材")
            check(snapshot().rows("mediaContext").single().getString("file")==video.getString("file"))
            ui.onNodeWithTag("clearChatContext").performClick();idle()
            ui.onNodeWithTag("chatImportMedia").performClick();Thread.sleep(1200)
            check(device.currentPackageName!="cn.xiyi.xystudio.nativeapp"){"System document picker did not open"}
            device.pressBack();waitText("AI 创作助手")
            // Real phone-local files are staged by ADB from existing project media, not fabricated results.
            for(name in listOf("qa-reference.png","qa-reference.mp4")) {
                val file=File(ui.activity.filesDir,name);check(file.isFile)
                ui.runOnIdle{vm.importMedia(Uri.fromFile(file),kind="auto",attachToChat=true)};idle()
                ui.waitUntil(30000){snapshot().rows("mediaContext").size==imported.size+1}
                val added=snapshot().rows("mediaContext").map{it.getString("file")}.first{it !in imported};imported.add(added)
            }
            waitText("下一条消息引用 2 份素材");shot("03-phone-imported-references")
            check(snapshot().rows("mediaContext").map{it.getString("kind")}.toSet()==setOf("image","video"))
            ui.onNodeWithTag("clearChatContext").performClick();idle()
            ui.onNodeWithTag("backToWorkspace").performClick()
            ui.onNodeWithTag("workspace:角色").performClick();ui.onNodeWithText("新建角色").performScrollTo().performClick()
            val name="附件回归角色-${System.currentTimeMillis()}"
            ui.onNodeWithTag("newAssetName").performTextInput(name)
            ui.onNodeWithText("创建",useUnmergedTree=true).performClick();idle();waitText(name)
            val asset=snapshot().getJSONObject("project").rows("assets").first{it.optString("name")==name}
            val assetId=asset.getString("id")
            ui.onNodeWithTag("moreAsset:$assetId").performScrollTo().performClick();ui.onNodeWithText("选择 / 替换图片").performClick()
            ui.waitUntil(20000){ui.onAllNodesWithTag("pickMedia:${imported.first()}").fetchSemanticsNodes().isNotEmpty()}
            ui.onNodeWithTag("pickMedia:${imported.first()}").performClick();idle()
            ui.waitUntil(20000){snapshot().getJSONObject("project").rows("assets").first{it.optString("id")==assetId}.optString("imageFile")==imported.first()}
            shot("04-created-asset")
            val shotId=rpc("asset.add",obj("kind" to "shots","name" to "附件回归分镜")) as String
            ui.onNodeWithTag("workspace:分镜").performClick()
            ui.waitUntil(15000){ui.onAllNodesWithTag("moreAsset:$shotId").fetchSemanticsNodes().isNotEmpty()}
            ui.onNodeWithTag("moreAsset:$shotId").performScrollTo().performClick();waitText("关联角色与场景");ui.onNodeWithText("关联角色与场景").performClick()
            ui.onNodeWithTag("linkAsset:$assetId").performClick();ui.onNodeWithText("保存关联").performClick();idle()
            check(snapshot().getJSONObject("project").rows("shots").first{it.optString("id")==shotId}.strings("assetIds").contains(assetId))
            shot("05-linked-shot")
            ui.onNodeWithTag("moreAsset:$shotId").performScrollTo().performClick();ui.onNodeWithText("删除条目").performClick();ui.onNodeWithText("确认删除").performClick();idle()
            ui.onNodeWithTag("workspace:角色").performClick()
            // Only delete the temporary item created by this test; original assets are never touched.
            ui.onNodeWithTag("moreAsset:$assetId").performScrollTo().performClick();ui.onNodeWithText("删除条目").performClick()
            ui.onNodeWithText("保留").performClick();check(snapshot().getJSONObject("project").rows("assets").any{it.optString("id")==assetId})
            ui.onNodeWithTag("moreAsset:$assetId").performClick();ui.onNodeWithText("删除条目").performClick();ui.onNodeWithText("确认删除").performClick();idle()
            check(snapshot().getJSONObject("project").rows("assets").none{it.optString("id")==assetId})
            ui.onNodeWithTag("nav:素材").performClick();waitText("素材库")
            ui.waitUntil(20000){ui.onAllNodesWithTag("trashMedia:${imported.first()}").fetchSemanticsNodes().isNotEmpty()}
            ui.onNodeWithTag("trashMedia:${imported.first()}").performScrollTo().performClick()
            ui.onNode(hasText("移入回收站") and hasAnyAncestor(isDialog()),useUnmergedTree=true).performClick();idle()
            ui.onNodeWithText("回收站").performClick();idle()
            ui.waitUntil(20000){ui.onAllNodesWithTag("trashMedia:${imported.first()}").fetchSemanticsNodes().isNotEmpty()}
            shot("06-media-trash")
            ui.onNodeWithTag("trashMedia:${imported.first()}").performScrollTo().performClick();idle()
            ui.onNodeWithText("回收站").performClick();idle()
            val after=snapshot().getJSONObject("project")
            check(after.rows("tasks").map{it.getString("id")}.toSet()==jobs);check(after.rows("chat").size==chats)
            ui.onNodeWithTag("nav:首页").performClick()
        } finally {
            rpc("context.clear")
            originalMedia.forEach{rpc("context.add_media",obj("file" to it.getString("file")))}
            originalIds.forEach{rpc("selection",obj("id" to it,"pin" to true))}
            rpc("selection",obj("id" to originalSelected))
        }
    }
}
