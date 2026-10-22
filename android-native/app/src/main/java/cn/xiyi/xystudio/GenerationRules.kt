package cn.xiyi.xystudio

import org.json.JSONObject

/** Form checks only. PC validation and workflow construction remain authoritative. */
object GenerationRules {
    fun referenceRange(mode: String): IntRange = when (mode) {
        "qwen_edit" -> 1..16
        "h3_ref" -> 1..9
        "h3_fl2v" -> 2..2
        "quad", "h3_i2v", "upscale" -> 1..1
        else -> 0..0
    }

    fun referenceHint(mode: String): String = when (mode) {
        "h3_i2v" -> "选择 1 张图片作为视频首帧。"
        "h3_fl2v" -> "需要 2 张图片：第 1 张是首帧，第 2 张是尾帧。"
        "h3_ref" -> "选择 1–9 张参考图，排列顺序对应提示词中的引用顺序。"
        "qwen_edit" -> "选择 1–16 张待编辑或参考图片。"
        else -> "选择 1 张原始图片。"
    }

    fun validate(g: JSONObject): String? {
        if (g.optString("mode") != "upscale" && g.optString("prompt").isBlank()) return "请填写提示词"
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
