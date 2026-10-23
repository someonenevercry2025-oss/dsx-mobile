package id.dsx.mobile.ui

import android.annotation.SuppressLint
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import java.io.File

private const val PLACEHOLDER_STYLE = """
<style id="dsx-placeholder-style">
  .dsx-ph {
    background: #fff3cd;
    color: #856404;
    border-bottom: 2px dashed #ffc107;
    padding: 0 2px;
  }
</style>
<script>
(function(){
  function walk(node){
    if(node.nodeType===3){
      var t=node.nodeValue;
      if(!t) return;
      var re=/(\[{1,2}[^\]]{0,80}\]{1,2}|\.{3,}|…+)/g;
      if(!re.test(t)) return;
      re.lastIndex=0;
      var frag=document.createDocumentFragment();
      var last=0,m;
      while((m=re.exec(t))){
        if(m.index>last) frag.appendChild(document.createTextNode(t.slice(last,m.index)));
        var s=document.createElement('span');
        s.className='dsx-ph';
        s.textContent=m[0];
        frag.appendChild(s);
        last=m.index+m[0].length;
      }
      if(last<t.length) frag.appendChild(document.createTextNode(t.slice(last)));
      node.parentNode.replaceChild(frag,node);
      return;
    }
    if(node.nodeType===1 && node.tagName!=='SCRIPT' && node.tagName!=='STYLE'){
      var kids=Array.prototype.slice.call(node.childNodes);
      kids.forEach(walk);
    }
  }
  walk(document.body);
})();
</script>
"""

private fun injectPlaceholderHighlight(html: String): String {
    val inject = PLACEHOLDER_STYLE
    return when {
        html.contains("</body>", ignoreCase = true) ->
            html.replace(Regex("</body>", RegexOption.IGNORE_CASE), "$inject</body>")
        html.contains("</html>", ignoreCase = true) ->
            html.replace(Regex("</html>", RegexOption.IGNORE_CASE), "$inject</html>")
        else -> html + inject
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun HtmlPreviewPane(
    htmlFile: File?,
    htmlContent: String? = null,
) {
    Column(Modifier.fillMaxSize()) {
        Box(
            Modifier
                .fillMaxWidth()
                .background(MaterialTheme.colorScheme.primaryContainer)
                .padding(horizontal = 12.dp, vertical = 6.dp),
        ) {
            Text(
                "Pratinjau perkiraan · placeholder [..] / .... ditandai kuning",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
        AndroidView(
            factory = { ctx ->
                WebView(ctx).apply {
                    webViewClient = WebViewClient()
                    settings.javaScriptEnabled = true
                    settings.allowFileAccess = true
                    settings.builtInZoomControls = true
                    settings.displayZoomControls = false
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                }
            },
            update = { webView ->
                val raw = when {
                    htmlFile != null && htmlFile.exists() ->
                        runCatching { htmlFile.readText() }.getOrNull()
                    !htmlContent.isNullOrBlank() -> htmlContent
                    else -> null
                }
                if (raw != null) {
                    val base = htmlFile?.parentFile?.let { "file://${it.absolutePath}/" }
                    webView.loadDataWithBaseURL(
                        base,
                        injectPlaceholderHighlight(raw),
                        "text/html",
                        "UTF-8",
                        null,
                    )
                } else {
                    webView.loadData(
                        "<p style='padding:16px;font-family:sans-serif;color:#666'>Belum ada pratinjau. Bangun HTML terlebih dahulu.</p>",
                        "text/html",
                        "UTF-8",
                    )
                }
            },
            modifier = Modifier.fillMaxSize(),
        )
    }
}
