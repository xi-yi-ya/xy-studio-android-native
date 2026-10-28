package cn.xiyi.xystudio

import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test

class GenerationRulesTest {
    private fun valid() = obj("mode" to "qwen", "prompt" to "A robot", "seed" to "9223372036854775807",
        "megapixels" to "0.2", "steps" to "4", "seconds" to "2", "scale" to "2", "cinema_strength" to "0.4", "references" to JSONArray())

    @Test fun preservesInt64SeedAndRejectsOverflow() {
        assertNull(GenerationRules.validate(valid()))
        assertTrue(GenerationRules.validate(valid().put("seed", "9223372036854775808"))!!.contains("种子"))
    }
    @Test fun rejectsMalformedNumbersAndOutOfRangeValues() {
        listOf("", "NaN", "Infinity", "0", "17").forEach {
            assertTrue(GenerationRules.validate(valid().put("megapixels", it))!!.contains("像素量"))
        }
        listOf("-1", "4.5", "101").forEach { assertTrue(GenerationRules.validate(valid().put("steps", it))!!.contains("采样步数")) }
    }
    @Test fun validatesFirstLastFramesAndReferenceCaps() {
        val g=valid().put("mode", "h3_fl2v").put("references",JSONArray(listOf("first.png")))
        assertTrue(GenerationRules.validate(g)!!.contains("2 张"))
        assertNull(GenerationRules.validate(g.put("references",JSONArray(listOf("first.png","last.png")))))
        assertNotNull(GenerationRules.validate(g.put("mode","h3_i2v")))
    }
    @Test fun upscaleMayHaveEmptyPromptButRequiresSource() {
        val g=valid().put("mode","upscale").put("prompt","")
        assertNotNull(GenerationRules.validate(g))
        assertNull(GenerationRules.validate(g.put("references",JSONArray(listOf("source.png")))))
    }
    private fun cloud()=valid().put("mode","pixstag_t2v").put("api_model","MiniMax-H3").put("api_resolution","720P").put("ratio","16:9").put("seconds","5")
    @Test fun cloudDoesNotRequireLocalSamplingFieldsAndEnforcesApiDuration() {
        assertNull(GenerationRules.validate(cloud().put("seed","").put("megapixels","").put("steps","")))
        listOf("2","4.5","31","NaN","").forEach { assertNotNull(GenerationRules.validate(cloud().put("seconds",it))) }
        assertTrue(GenerationRules.isVideo("pixstag_t2v"))
        assertNotNull(GenerationRules.validate(cloud().put("api_model","invalid")))
        assertNotNull(GenerationRules.validate(cloud().put("ratio","2:3")))
    }
    @Test fun cloudSupportsFirstLastFramesAndVideoOnlyReference() {
        assertNotNull(GenerationRules.validate(cloud().put("mode","pixstag_fl2v").put("references",JSONArray(listOf("a.png")))))
        assertNull(GenerationRules.validate(cloud().put("mode","pixstag_fl2v").put("references",JSONArray(listOf("a.png","b.png")))))
        assertNull(GenerationRules.validate(cloud().put("mode","pixstag_ref").put("video_references",JSONArray(listOf("clip.mp4")))))
        assertNotNull(GenerationRules.validate(cloud().put("mode","pixstag_ref")))
        assertNotNull(GenerationRules.validate(cloud().put("video_references",JSONArray(listOf("clip.mp4")))))
    }
}
