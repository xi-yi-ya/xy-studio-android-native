package cn.xiyi.handbook;

import java.net.URI;
import java.util.*;
import java.util.concurrent.*;
import java.util.function.Consumer;

/**
 * XY Studio 原生客户端的 Java 阅读模型。
 * <p>本文件帮助 Java 开发者理解 Kotlin 源码，使用 JDK 21 可编译。
 * 它不是 Android 应用的替代实现，不绘制 Compose UI，不连接 PC，不生成虚假结果。
 * Map 代表生产代码的 JSONObject；Transport、Screen、Player 是教学用接口，生产代码分别使用 OkHttp、Compose、Media3。
 * <p>阅读顺序：MainActivity → StudioShell → StudioViewModel → LanApi。
 * 生成流程继续看 GenerationScreen、GenerationRules；AI 附件看 ChatAttachments。
 */
public final class StudioJavaGuide {
    private StudioJavaGuide() {}

    /** 对应 MainActivity.kt：Android 调用 onCreate，随后建立主题和界面。 */
    public static final class MainActivity {
        /** 教学模型：实际 onCreate 的 Bundle、super 和 Android 生命周期由真实 Activity 提供。 */
        public void onCreate(Screen screen, StudioViewModel vm) {
            screen.show(new StudioShell(vm));
        }
    }

    /** 教学接口：Compose 的 setContent 不等同于传统 setContentView，本接口仅表达显示职责。 */
    public interface Screen { void show(StudioShell shell); }

    /** 对应 StudioShell.kt：导航、首页、创作工作区和 AI 悬浮入口。 */
    public static final class StudioShell {
        private final StudioViewModel vm;
        public StudioShell(StudioViewModel vm) { this.vm = vm; }
        /** 点击底部标签相当于改变 ViewModel 的 page，Compose 自动重新读取状态。 */
        public void selectTab(String page) { vm.page = page; }
        /** 从创作页进入 AI；返回时恢复此前页面。 */
        public void openAssistant() { vm.assistantReturnPage = vm.page; vm.page = "AI"; }
        public void closeAssistant() { vm.page = vm.assistantReturnPage; }
        public void generateImage() { vm.openGeneration("image"); }
        public void generateVideo() { vm.openGeneration("video"); }
    }

    /** 对应 StudioTheme.kt：颜色和卡片样式，ARGB 的 FF 表示不透明。 */
    public static final class StudioTheme {
        public static final int BACKGROUND = 0xFFF8F9FB;
        public static final int PRIMARY = 0xFF168F98;
        public static final int TEXT = 0xFF20252B;
        private StudioTheme() {}
    }

    /** 对应 HTTP /rpc 的信封；payload 是业务参数，不包含 DeepSeek API Key。 */
    public record RpcEnvelope(String id, String command, Map<String, Object> payload,
                              String projectId, int revision) {}

    /**
     * 返回值模型。生产 JSON 使用 ok、error、result、state 字段。
     * result 的类型依命令不同而不同，不能强行当成同一种业务对象。
     */
    public record RpcResponse(boolean ok, String error, Object result, Map<String, Object> state) {}

    /** PC 最新状态的教学表示；state 在生产代码中仍是完整 JSONObject。 */
    public record Snapshot(Map<String, Object> state) {}

    /**
     * 传输抽象，不提供假实现。真实 LanApi.kt 使用 OkHttp 阻塞请求并放在 IO 协程执行。
     * <p>POST /pair 用固定连接密码换取令牌；POST /rpc 需要 Bearer 令牌。
     * /events 是独立 WebSocket：连接后先发送令牌，再接收真实状态。
     */
    public interface Transport {
        String pair(String base, String password, String deviceName) throws Exception;
        RpcResponse rpc(String base, String token, RpcEnvelope request) throws Exception;
    }

    /** 对应 LanApi.kt：地址约束、认证、统一命令请求。 */
    public static final class LanApi {
        private final Transport transport;
        private String base = "";
        private String token = "";
        public LanApi(Transport transport) { this.transport = transport; }
        /**
         * 与当前 Kotlin 校验规则对应：私网/回环 IPv4、http、无账号/路径/查询串。
         * <p>127.x 只用于本机测试，手机里的 127.0.0.1 不指向 Windows。
         * @param input PC 局域网地址
         * @return 补全端口后的地址，默认 8765
         */
        public static String validateBase(String input) {
            URI uri = URI.create(input.contains("://") ? input.trim() : "http://" + input.trim());
            String[] parts = uri.getHost() == null ? new String[0] : uri.getHost().split("\\.");
            int[] ip = new int[4];
            boolean valid = parts.length == 4;
            if (valid) {
                try {
                    for (int i = 0; i < 4; i++) {
                        ip[i] = Integer.parseInt(parts[i]);
                        valid &= ip[i] >= 0 && ip[i] <= 255;
                    }
                } catch (NumberFormatException e) { valid = false; }
            }
            boolean local = valid && (ip[0] == 10 || ip[0] == 127 ||
                (ip[0] == 192 && ip[1] == 168) || (ip[0] == 172 && ip[1] >= 16 && ip[1] <= 31));
            boolean pathOk = uri.getPath() == null || uri.getPath().isEmpty() || uri.getPath().equals("/");
            if (!(local && "http".equals(uri.getScheme()) && uri.getUserInfo() == null &&
                uri.getQuery() == null && uri.getFragment() == null && pathOk &&
                (uri.getPort() == -1 || uri.getPort() >= 1 && uri.getPort() <= 65535))) {
                throw new IllegalArgumentException("请输入 PC 局域网 IPv4 与端口");
            }
            return "http://" + uri.getHost() + ":" + (uri.getPort() == -1 ? 8765 : uri.getPort());
        }
        public void pair(String address, String password, String name) throws Exception {
            base = validateBase(address);
            token = "";
            token = transport.pair(base, password, name);
        }
        public RpcResponse rpc(String command, Map<String, Object> payload, String projectId, int revision) throws Exception {
            return transport.rpc(base, token, new RpcEnvelope(UUID.randomUUID().toString(), command, payload, projectId, revision));
        }
        /** 只允许 PC 授权后发来的 /media/ 地址，不把任意 PC 磁盘路径作为 URL。 */
        public String media(String value) { return value.startsWith("/media/") ? base + value : ""; }
    }

    /**
     * 对应 StudioViewModel.kt 的核心职责。此处用两个 Executor 解释后台工作与 UI 回调。
     * <p>生产实现是 viewModelScope + Dispatchers.IO + Mutex。这里不复制生命周期取消、
     * WebSocket 重连、加密保存及完整异常处理；它是读代码的路线图，不能直接替换生产类。
     * <p>构造时 worker 应为串行 Executor，ui 应把工作派发到 UI 线程。
     */
    public static final class StudioViewModel {
        private final LanApi api;
        private final Executor worker;
        private final Executor ui;
        private final Consumer<Snapshot> render;
        public String page = "首页";
        public String assistantReturnPage = "创作";
        public String error = "";
        public boolean working;
        public String projectId;
        public int revision;
        public String generationReviewId;
        public String generationTarget;
        public Object generation;
        public StudioViewModel(LanApi api, Executor worker, Executor ui, Consumer<Snapshot> render) {
            this.api = api; this.worker = worker; this.ui = ui; this.render = render;
        }
        /** UI 发起命令，工作线程调用网络，UI 线程接收真实状态与结果。 */
        public void command(String name, Map<String, Object> payload, Consumer<Object> done) {
            if (working) return;
            working = true; error = "";
            String expectedProject = projectId;
            int expectedRevision = revision;
            worker.execute(() -> {
                try {
                    RpcResponse response = api.rpc(name, payload, expectedProject, expectedRevision);
                    ui.execute(() -> {
                        try {
                            if (response.state() != null) receive(new Snapshot(response.state()));
                            if (!response.ok()) throw new IllegalStateException(response.error());
                            done.accept(response.result());
                        } catch (Exception e) { error = e.getMessage(); }
                        finally { working = false; }
                    });
                } catch (Exception e) {
                    ui.execute(() -> { error = e.getMessage(); working = false; });
                }
            });
        }
        /** 对应 receive：消费 PC 发来的状态。真实代码还清理项目切换时的旧素材与弹窗。 */
        public void receive(Snapshot next) {
            if (next.state().get("lanRevision") instanceof Number n) revision = n.intValue();
            Object project = next.state().get("project");
            projectId = project instanceof Map<?, ?> p && p.get("id") instanceof String id ? id : null;
            render.accept(next);
        }
        /** 真实 openGeneration 还分页取得当前项目的参考图片。 */
        public void openGeneration(String kind) {
            command("generation.defaults", Map.of("kind", kind), result -> generation = result);
        }
        /** 用户在确认页点击提交后才调用；Agent 提案走原来的审阅接口。 */
        public void submitGeneration(Map<String, Object> value) {
            Map<String, Object> payload = new LinkedHashMap<>();
            String name;
            if (generationReviewId != null) {
                name = "review.respond";
                payload.put("id", generationReviewId); payload.put("accepted", true);
            } else {
                name = "generation.submit";
                payload.put("target", generationTarget);
            }
            payload.put("generation", value);
            command(name, payload, result -> {
                generation = null; generationReviewId = null; generationTarget = null; page = "任务";
            });
        }
    }

    /** 对应 GenerationRules.kt：表单校验的 Java 对照；PC 仍进行最终校验。 */
    public static final class GenerationRules {
        private GenerationRules() {}
        /** 首尾帧必须恰好两张，文生图/文生视频无图片引用。 */
        public static int[] referenceRange(String mode) {
            return switch (mode) {
                case "qwen_edit" -> new int[]{1, 16};
                case "h3_ref" -> new int[]{1, 9};
                case "h3_fl2v" -> new int[]{2, 2};
                case "quad", "h3_i2v", "upscale" -> new int[]{1, 1};
                default -> new int[]{0, 0};
            };
        }
        public static String referenceHint(String mode) {
            return switch (mode) {
                case "h3_i2v" -> "选择 1 张图片作为视频首帧。";
                case "h3_fl2v" -> "需要 2 张图片：第 1 张是首帧，第 2 张是尾帧。";
                case "h3_ref" -> "选择 1–9 张参考图，排列顺序对应提示词中的引用顺序。";
                case "qwen_edit" -> "选择 1–16 张待编辑或参考图片。";
                default -> "选择 1 张原始图片。";
            };
        }
        /**
         * null 表示通过；文本表示错误。数字输入暂存为字符串，避免输入过程中强制转换崩溃。
         * <p>这是对应当前字段的 Java 实现；Map 与 JSONObject 对空值/数字的细节并非完全相同。
         */
        public static String validate(Map<String, Object> g) {
            String mode = string(g, "mode");
            if (!mode.equals("upscale") && string(g, "prompt").isBlank()) return "请填写提示词";
            try { if (Long.parseLong(string(g, "seed")) < 0) return "种子必须为非负整数"; }
            catch (NumberFormatException e) { return "种子必须为非负 Long 整数"; }
            if (!inRange(g, "megapixels", 0.1, 16.0)) return "像素量需在 0.1–16 MP 之间";
            try {
                int steps = Integer.parseInt(string(g, "steps"));
                if (steps < 0 || steps > 100) return "采样步数需为 0–100 的整数";
            } catch (NumberFormatException e) { return "采样步数需为 0–100 的整数"; }
            if (!inRange(g, "seconds", 0.2, 149.0)) return "视频时长需在 0.2–149 秒之间";
            if (!inRange(g, "scale", 1, 8)) return "放大倍率需在 1–8 之间";
            if (!inRange(g, "cinema_strength", 0, 2)) return "电影 LoRA 强度需在 0–2 之间";
            int count = g.get("references") instanceof List<?> refs ? refs.size() : 0;
            int[] range = referenceRange(mode);
            return count < range[0] || count > range[1] ? referenceHint(mode) : null;
        }
        private static String string(Map<String, Object> g, String key) { return Objects.toString(g.get(key), ""); }
        private static boolean inRange(Map<String, Object> g, String key, double min, double max) {
            try { double n = Double.parseDouble(string(g, key)); return Double.isFinite(n) && n >= min && n <= max; }
            catch (NumberFormatException e) { return false; }
        }
    }

    /** 对应 GenerationScreen.kt：编辑 → 校验 → PC 预览参数 → 用户确认 → 提交。 */
    public static final class GenerationScreen {
        private final StudioViewModel vm;
        public GenerationScreen(StudioViewModel vm) { this.vm = vm; }
        /** 这里只请求输出尺寸/步数等参数，不运行模型；UI 在回调里显示确认框。 */
        public void next(Map<String, Object> parameters, Consumer<Object> showConfirmation) {
            String error = GenerationRules.validate(parameters);
            if (error != null) throw new IllegalArgumentException(error);
            vm.command("generation.preview", Map.of("generation", parameters), showConfirmation);
        }
        /** 必须由最终确认按钮调用，不能在渲染页面时自动执行。 */
        public void confirm(Map<String, Object> parameters) { vm.submitGeneration(parameters); }
    }

    /** 对应 CreationScreens.kt：任务列表和 AI 会话共处此文件。 */
    public static final class CreationScreens {
        private final StudioViewModel vm;
        public CreationScreens(StudioViewModel vm) { this.vm = vm; }
        public void sendChat(String text) { vm.command("chat.send", Map.of("text", text), result -> {}); }
        public void cancelTaskAfterConfirmation(String taskId) { vm.command("task.cancel", Map.of("id", taskId), result -> {}); }
        public void resumeQuery(String taskId) { vm.command("task.resume", Map.of("id", taskId), result -> {}); }
    }

    /** 对应 ChatAttachments.kt：引用的是 PC 项目真实素材。移除引用不删除文件。 */
    public static final class ChatAttachments {
        private final StudioViewModel vm;
        public ChatAttachments(StudioViewModel vm) { this.vm = vm; }
        public void attach(String file) { vm.command("context.add_media", Map.of("file", file), result -> {}); }
        public void remove(String file) { vm.command("context.remove", Map.of("file", file), result -> {}); }
        /** 手机导入在真实代码中由系统选择器提供 Uri，再调用 importMedia；不是任意磁盘路径。 */
        public static final int MAX_UPLOAD_BYTES = 100 * 1024 * 1024;
    }

    /** 对应 MediaPicker.kt：有独立分页/搜索状态；切换项目时关闭选择器。 */
    public static final class MediaPicker {
        private final StudioViewModel vm;
        public MediaPicker(StudioViewModel vm) { this.vm = vm; }
        public void load(String kind, String query, int offset, Consumer<Object> displayItems) {
            vm.command("library.query", Map.of("kind", kind, "query", query, "offset", offset, "limit", 40), displayItems);
        }
    }

    /** 对应 LibraryFilters.kt：只是查询条件，不改变原始素材。 */
    public record LibraryFilters(String kind, String source, String owner, String sort, boolean trash) {
        public Map<String, Object> payload(String query, int offset) {
            return Map.of("kind", kind, "source", source, "owner", owner, "sort", sort,
                          "trash", trash, "query", query, "offset", offset, "limit", 40);
        }
    }

    /** 对应 WorkspaceActions.kt：资产操作菜单；修改统一交给 PC。 */
    public static final class WorkspaceActions {
        private final StudioViewModel vm;
        public WorkspaceActions(StudioViewModel vm) { this.vm = vm; }
        public void useMedia(String assetId, String file) { vm.command("asset.use_media", Map.of("id", assetId, "file", file), result -> {}); }
        /** 真实对话框在打开时捕获 revision，避免覆盖后来发生的修改。 */
        public void deleteAfterConfirmation(String assetId) { vm.command("asset.delete", Map.of("id", assetId), result -> {}); }
    }

    /**
     * 对应 ConnectionStore.kt 的职责接口。生产代码用 AndroidKeyStore + AES/GCM 加密 SharedPreferences。
     * <p>此接口不实现加密，不应使用普通文件/明文属性替代它；保存的是 LAN 密码，不是 DeepSeek 密钥。
     */
    public interface ConnectionStore {
        void save(String base, String password, String deviceName);
        Optional<Connection> load();
        void clear();
    }
    public record Connection(String base, String password, String deviceName) {}

    /** 对应 MediaDialog.kt：生命周期变化时暂停，关闭预览时释放解码器。 */
    public static final class MediaDialog implements AutoCloseable {
        private final Player player;
        public MediaDialog(Player player) { this.player = player; }
        public void onStop() { player.pause(); }
        @Override public void close() { player.release(); }
    }
    /** 教学接口；生产播放器是 androidx.media3.exoplayer.ExoPlayer。 */
    public interface Player { void pause(); void release(); }
}
