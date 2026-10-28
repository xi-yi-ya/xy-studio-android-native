package cn.xiyi.xystudio

import org.json.JSONObject

/** Form checks only. PC validation and workflow construction remain authoritative. */
object GenerationRules {
    fun isCloud(mode: String) = mode.startsWith("pixstag_")
    fun isVideo(mode: String) = mode.startsWith("h3") || isCloud(mode)
    fun referenceRange(mode: String): IntRange = when (mode) {
        "qwen_edit" -> 1..16
        "h3_ref" -> 1..9
        "pixstag_ref" -> 0..9
        "h3_fl2v", "pixstag_fl2v" -> 2..2
        "quad", "h3_i2v", "pixstag_i2v", "upscale" -> 1..1
        else -> 0..0
    }

    fun referenceHint(mode: String): String = when (mode) {
        "h3_i2v", "pixstag_i2v" -> "选择 1 张图片作为视频首帧。"
        "h3_fl2v", "pixstag_fl2v" -> "需要 2 张图片：第 1 张是首帧，第 2 张是尾帧。"
        "pixstag_ref" -> "选择参考图片和/或视频，至少 1 份；图片最多 9 张，视频最多 3 个。"
        "h3_ref" -> "选择 1–9 张参考图，排列顺序对应提示词中的引用顺序。"
        "qwen_edit" -> "选择 1–16 张待编辑或参考图片。"
        else -> "选择 1 张原始图片。"
    }

    fun validate(g: JSONObject): String? {
        if (g.optString("mode") != "upscale" && g.optString("prompt").isBlank()) return "请填写提示词"
        if (isCloud(g.optString("mode"))) {
            if(g.optString("prompt").codePointCount(0,g.optString("prompt").length)>5000)return "Pixstag 提示词最多 5000 个字符"
            val seconds=g.optString("seconds").toDoubleOrNull()
            if(seconds==null || !seconds.isFinite() || seconds !in 4.0..30.0 || seconds%1.0!=0.0)return "Pixstag 时长须为 4–30 的整数秒"
            if(g.optString("api_model") !in listOf("MiniMax-H3","doubao-seedance-2","doubao-seedance-2-5"))return "请选择 Pixstag 模型"
            if(g.optString("api_resolution") !in listOf("720P","768P","1080P","2K"))return "请选择 Pixstag 清晰度"
            if(g.optString("ratio") !in listOf("adaptive","21:9","16:9","4:3","1:1","3:4","9:16"))return "Pixstag 不支持该比例"
            val range=referenceRange(g.optString("mode"))
            if(g.strings("references").size !in range)return referenceHint(g.optString("mode"))
            val videos=g.strings("video_references")
            if(videos.size>(if(g.optString("mode")=="pixstag_ref")3 else 0))return "仅多模态模式支持参考视频，最多 3 个"
            if(g.optString("mode")=="pixstag_ref" && g.strings("references").isEmpty() && videos.isEmpty())return referenceHint("pixstag_ref")
            return null
        }
        if (g.optString("seed").toLongOrNull()?.let { it >= 0 } != true) return "种子必须为 0 至 9223372036854775807 的整数"
        if (g.optDouble("megapixels").let { !it.isFinite() || it !in 0.1..16.0 }) return "像素量需在 0.1–16 MP 之间"
        if (g.optString("steps").toIntOrNull()?.let { it in 0..100 } != true) return "采样步数需为 0–100 的整数"
        if (g.optDouble("seconds").let { !it.isFinite() || it !in 0.2..149.0 }) return "视频时长需在 0.2–149 秒之间"
        if (g.optDouble("scale").let { !it.isFinite() || it !in 1.0..8.0 }) return "放大倍率需在 1–8 之间"
        if (g.optDouble("cinema_strength").let { !it.isFinite() || it !in 0.0..2.0 }) return "电影 LoRA 强度需在 0–2 之间"
        val range = referenceRange(g.optString("mode"))
        if (g.strings("references").size !in range) return referenceHint(g.optString("mode"))
        return null
    }
}
