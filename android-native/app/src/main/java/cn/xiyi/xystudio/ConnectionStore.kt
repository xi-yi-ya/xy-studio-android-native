package cn.xiyi.xystudio

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import org.json.JSONObject

/** Stores only the LAN connection password, encrypted by the Android Keystore. */
class ConnectionStore(context:Context) {
    private val prefs=context.getSharedPreferences("lan-secure",Context.MODE_PRIVATE)
    private val alias="xy-studio-lan-connection"
    private fun key():SecretKey {
        val store=KeyStore.getInstance("AndroidKeyStore").apply{load(null)}
        (store.getKey(alias,null) as? SecretKey)?.let{return it}
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore").apply {
            init(KeyGenParameterSpec.Builder(alias,KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        }.generateKey()
    }
    fun save(base:String,password:String,name:String) {
        val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply{init(Cipher.ENCRYPT_MODE,key())}
        val data=cipher.doFinal(obj("base" to base,"password" to password,"name" to name).toString().toByteArray(Charsets.UTF_8))
        prefs.edit().putString("iv",Base64.encodeToString(cipher.iv,Base64.NO_WRAP))
            .putString("value",Base64.encodeToString(data,Base64.NO_WRAP)).apply()
    }
    fun load():JSONObject? {
        val value=prefs.getString("value",null) ?: return null
        return try {
            val cipher=Cipher.getInstance("AES/GCM/NoPadding").apply{init(Cipher.DECRYPT_MODE,key(),GCMParameterSpec(128,Base64.decode(prefs.getString("iv",""),Base64.NO_WRAP)))}
            JSONObject(String(cipher.doFinal(Base64.decode(value,Base64.NO_WRAP)),Charsets.UTF_8))
        } catch(_:Exception){clear();null}
    }
    fun clear(){prefs.edit().clear().apply()}
}
