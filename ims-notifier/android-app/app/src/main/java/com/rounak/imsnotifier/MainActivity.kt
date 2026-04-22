package com.rounak.imsnotifier

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.google.android.material.snackbar.Snackbar
import com.google.firebase.messaging.FirebaseMessaging
import com.rounak.imsnotifier.databinding.ActivityMainBinding
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import androidx.lifecycle.lifecycleScope
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var prefs: SharedPreferences

    private val notifPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            fetchAndRegisterToken()
        } else {
            Snackbar.make(
                binding.root,
                "Without notification permission you won't see push alerts.",
                Snackbar.LENGTH_LONG
            ).show()
        }
    }

    private val latestReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            intent ?: return
            val date = intent.getStringExtra("date").orEmpty()
            val text = intent.getStringExtra("text").orEmpty()
            val link = intent.getStringExtra("link").orEmpty()
            showLatest(date, text, link)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        prefs = getSharedPreferences("ims_notifier", MODE_PRIVATE)

        binding.backendUrl.text = BuildConfig.BACKEND_URL
        binding.refreshButton.setOnClickListener { ensurePermissionThenRegister() }
        binding.openDashboardButton.setOnClickListener {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(BuildConfig.BACKEND_URL)))
        }

        // Restore last-seen notification shown in UI
        val lastDate = prefs.getString("last_date", null)
        val lastText = prefs.getString("last_text", null)
        val lastLink = prefs.getString("last_link", null)
        if (!lastText.isNullOrBlank()) {
            showLatest(lastDate.orEmpty(), lastText, lastLink.orEmpty())
        }

        ensurePermissionThenRegister()
    }

    override fun onStart() {
        super.onStart()
        LocalBroadcastManager.getInstance(this).registerReceiver(
            latestReceiver, IntentFilter("ims.notification.received")
        )
    }

    override fun onStop() {
        super.onStop()
        LocalBroadcastManager.getInstance(this).unregisterReceiver(latestReceiver)
    }

    private fun ensurePermissionThenRegister() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notifPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                return
            }
        }
        fetchAndRegisterToken()
    }

    private fun fetchAndRegisterToken() {
        binding.statusText.text = getString(R.string.status_fetching)
        FirebaseMessaging.getInstance().token.addOnCompleteListener { task ->
            if (!task.isSuccessful || task.result == null) {
                binding.statusText.text = getString(R.string.status_fcm_failed)
                return@addOnCompleteListener
            }
            val token = task.result!!
            prefs.edit().putString("fcm_token", token).apply()
            binding.tokenPreview.text = token.take(24) + "..."
            registerTokenWithBackend(token)
        }
    }

    private fun registerTokenWithBackend(token: String) {
        lifecycleScope.launch {
            val ok = withContext(Dispatchers.IO) {
                try {
                    val client = OkHttpClient()
                    val body = JSONObject().put("fcm_token", token).toString()
                        .toRequestBody("application/json".toMediaType())
                    val req = Request.Builder()
                        .url("${BuildConfig.BACKEND_URL}/api/device")
                        .post(body)
                        .build()
                    client.newCall(req).execute().use { it.isSuccessful }
                } catch (e: Exception) {
                    false
                }
            }
            binding.statusText.text = if (ok) {
                getString(R.string.status_registered)
            } else {
                getString(R.string.status_backend_failed)
            }
        }
    }

    private fun showLatest(date: String, text: String, link: String) {
        binding.latestCard.visibility = android.view.View.VISIBLE
        binding.latestDate.text = if (date.isNotBlank()) date else "—"
        binding.latestText.text = text
        if (link.isNotBlank()) {
            binding.latestLink.text = link
            binding.latestLink.visibility = android.view.View.VISIBLE
            binding.latestLink.setOnClickListener {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(link)))
            }
        } else {
            binding.latestLink.visibility = android.view.View.GONE
        }
    }
}
