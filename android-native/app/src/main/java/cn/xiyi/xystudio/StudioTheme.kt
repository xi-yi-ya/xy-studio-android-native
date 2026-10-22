package cn.xiyi.xystudio

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
fun StudioTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Color(0xFF168F98), onPrimary = Color.White,
            primaryContainer = Color(0xFFE5F3F4), onPrimaryContainer = Color(0xFF14666D),
            secondary = Color(0xFF647781), onSecondary = Color.White,
            secondaryContainer = Color(0xFFEDF3F4), onSecondaryContainer = Color(0xFF43545D),
            background = Color(0xFFF8F9FB), onBackground = Color(0xFF20252B),
            surface = Color.White, onSurface = Color(0xFF20252B),
            surfaceVariant = Color(0xFFF1F4F6), onSurfaceVariant = Color(0xFF69757F),
            surfaceContainer = Color.White, surfaceContainerLow = Color.White,
            surfaceContainerHigh = Color(0xFFF5F7F9), surfaceContainerHighest = Color(0xFFF1F4F6),
            outline = Color(0xFFC6D0D7), outlineVariant = Color(0xFFE4E9ED),
            error = Color(0xFFB65D65), onError = Color.White,
            errorContainer = Color(0xFFFAECEE), onErrorContainer = Color(0xFF87454C)
        ),
        typography = Typography(
            headlineSmall = TextStyle(fontSize = 26.sp, lineHeight = 34.sp, fontWeight = FontWeight.Bold),
            titleLarge = TextStyle(fontSize = 22.sp, lineHeight = 30.sp, fontWeight = FontWeight.SemiBold),
            titleMedium = TextStyle(fontSize = 17.sp, lineHeight = 25.sp, fontWeight = FontWeight.SemiBold),
            bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 25.sp),
            bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 22.sp),
            bodySmall = TextStyle(fontSize = 12.sp, lineHeight = 19.sp),
            labelLarge = TextStyle(fontSize = 14.sp, lineHeight = 20.sp, fontWeight = FontWeight.Medium),
            labelMedium = TextStyle(fontSize = 12.sp, lineHeight = 18.sp, fontWeight = FontWeight.Medium),
            labelSmall = TextStyle(fontSize = 11.sp, lineHeight = 16.sp, fontWeight = FontWeight.Medium)
        ), content = content
    )
}

@Composable
fun StudioCard(
    modifier: Modifier = Modifier,
    shape: androidx.compose.ui.graphics.Shape = RoundedCornerShape(20.dp),
    colors: CardColors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
    content: @Composable ColumnScope.() -> Unit
) = Card(modifier, shape = shape, colors = colors,
    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant), content = content)

/** Small original outline glyphs; no downloaded artwork or extra icon dependency. */
@Composable
fun StudioIcon(name: String, modifier: Modifier = Modifier, tint: Color = LocalContentColor.current) {
    Canvas(modifier.size(24.dp)) {
        val u = size.minDimension / 24f
        val stroke = Stroke(1.7f * u, cap = StrokeCap.Round)
        fun line(x: Float, y: Float, x2: Float, y2: Float) = drawLine(tint, Offset(x*u,y*u),Offset(x2*u,y2*u),1.7f*u,StrokeCap.Round)
        fun path(vararg points: Pair<Float,Float>) {
            val p=Path(); points.forEachIndexed { i,v -> if(i==0)p.moveTo(v.first*u,v.second*u) else p.lineTo(v.first*u,v.second*u) };drawPath(p,tint,style=stroke)
        }
        fun box(x:Float,y:Float,w:Float,h:Float) = drawRoundRect(tint,Offset(x*u,y*u),Size(w*u,h*u),CornerRadius(2*u),style=stroke)
        when(name) {
            "首页" -> { path(3f to 10f,12f to 3f,21f to 10f);path(5f to 9f,5f to 21f,19f to 21f,19f to 9f);box(9f,13f,6f,8f) }
            "创作","分镜" -> { box(3f,8f,18f,13f);path(3f to 8f,2f to 4f,20f to 1f,21f to 6f,3f to 9f);line(8f,3f,11f,7f);line(14f,2f,17f,6f);line(3f,12f,21f,12f) }
            "素材","image" -> { box(3f,3f,18f,18f);drawCircle(tint,2*u,Offset(8*u,8*u),style=stroke);path(4f to 18f,10f to 12f,14f to 16f,17f to 13f,21f to 17f) }
            "video" -> { box(3f,3f,18f,18f);line(7f,3f,7f,21f);line(17f,3f,17f,21f);listOf(8f,15f).forEach{line(3f,it,7f,it);line(17f,it,21f,it)} }
            "任务" -> { listOf(5f,12f,19f).forEach{path(3f to it,5f to it+2,8f to it-2);line(12f,it,21f,it)} }
            "AI" -> { path(12f to 3f,14.5f to 9.5f,21f to 12f,14.5f to 14.5f,12f to 21f,9.5f to 14.5f,3f to 12f,9.5f to 9.5f,12f to 3f);line(20f,2f,20f,6f);line(18f,4f,22f,4f) }
            "项目" -> { path(3f to 7f,3f to 4f,9f to 4f,12f to 7f);box(3f,7f,18f,14f) }
            "back" -> {path(10f to 5f,3f to 12f,10f to 19f);line(3f,12f,21f,12f)}
            "arrow" -> {line(4f,12f,20f,12f);path(14f to 6f,20f to 12f,14f to 18f)}
            "connection" -> {drawArc(tint,220f,100f,false,Offset(2*u,5*u),Size(20*u,20*u),style=stroke);drawArc(tint,220f,100f,false,Offset(6*u,10*u),Size(12*u,12*u),style=stroke);drawCircle(tint,1.5f*u,Offset(12*u,19*u))}
            else -> {drawCircle(tint,8*u,center,style=stroke);line(12f,8f,12f,16f);line(8f,12f,16f,12f)}
        }
    }
}
