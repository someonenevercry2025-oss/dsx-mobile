package id.dsx.mobile.bridge

import com.google.gson.JsonObject

/** Aman terhadap JsonNull / tipe tak terduga (JsonNull.asString melempar exception). */
fun JsonObject.optString(key: String): String? =
    get(key)?.takeIf { it.isJsonPrimitive }?.asString

fun JsonObject.optInt(key: String): Int? =
    get(key)?.takeIf { it.isJsonPrimitive }?.let { runCatching { it.asInt }.getOrNull() }
