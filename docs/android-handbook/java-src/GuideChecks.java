package cn.xiyi.handbook;
import java.util.*;

/** Java 阅读模型的纯逻辑自检，不连接 PC、不修改项目、不调用模型。 */
public final class GuideChecks {
    private static int checks;
    private static void check(boolean ok) { checks++; if(!ok) throw new AssertionError("Check " + checks); }
    public static void main(String[] args) {
        check(StudioJavaGuide.LanApi.validateBase("192.168.1.2").equals("http://192.168.1.2:8765"));
        for(String bad : List.of("https://192.168.1.2", "8.8.8.8", "http://192.168.1.2/secret", "http://user@192.168.1.2", "http://192.168.1.2?key=value")) {
            boolean rejected=false;
            try { StudioJavaGuide.LanApi.validateBase(bad); } catch(IllegalArgumentException e) { rejected=true; }
            check(rejected);
        }
        Map<String,Object> g=new HashMap<>();
        g.put("mode","h3_i2v");g.put("prompt","教学校验，不会发送");g.put("seed","42");
        g.put("megapixels","1");g.put("steps","0");g.put("seconds","2");g.put("scale","2");
        g.put("cinema_strength","1");g.put("references",List.of("example-only.png"));
        check(StudioJavaGuide.GenerationRules.validate(g)==null);
        g.put("references",List.of());check(StudioJavaGuide.GenerationRules.validate(g)!=null);
        g.put("references",List.of("example-only.png"));g.put("seed","9223372036854775808");
        check(StudioJavaGuide.GenerationRules.validate(g)!=null);
        g.put("seed","42");g.put("megapixels","NaN");check(StudioJavaGuide.GenerationRules.validate(g)!=null);
        int[] range=StudioJavaGuide.GenerationRules.referenceRange("h3_fl2v");check(range[0]==2&&range[1]==2);
        System.out.println("PASS: "+checks+" Java guide checks; no network or project writes.");
    }
}
