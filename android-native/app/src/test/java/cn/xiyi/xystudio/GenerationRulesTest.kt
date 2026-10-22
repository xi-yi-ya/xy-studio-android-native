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
}
