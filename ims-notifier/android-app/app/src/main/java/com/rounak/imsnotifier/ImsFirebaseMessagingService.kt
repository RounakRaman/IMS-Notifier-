package com.rounak.imsnotifier

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.localbroadcastmanager.content.LocalBroadcastManager
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import kotlin.random.Random

class ImsFirebaseMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        getSharedPreferences("ims_notifier", Context.MODE_PRIVATE)
            .edit().putString("fcm_token", token).apply()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val client = OkHttpClient()
                val body = JSONObject().put("fcm_token", token).toString()
                    .toRequestBody("application/json".toMediaType())
                val req = Request.Builder()
                    .url("${BuildConfig.BACKEND_URL}/api/device")
                    .post(body)
                    .build()
                client.newCall(req).execute().close()
            } catch (_: Exception) {
                // Best-effort; MainActivity will retry on next launch.
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)

        val data = message.data
        val date = data["date"].orEmpty()
        val text = data["text"] ?: message.notification?.body.orEmpty()
        val link = data["link"].orEmpty()
        val title = message.notification?.title ?: "New IMS Notification"

        // Save for display inside the app
        getSharedPreferences("ims_notifier", Context.MODE_PRIVATE).edit()
            .putString("last_date", date)
            .putString("last_text", text)
            .putString("last_link", link)
            .apply()

        // Post to any open MainActivity
        val broadcast = Intent("ims.notification.received").apply {
            putExtra("date", date)
            putExtra("text", text)
            putExtra("link", link)
        }
        LocalBroadcastManager.getInstance(this).sendBroadcast(broadcast)

        showNotification(title, if (date.isNotBlank()) "[$date] $text" else text, link)
    }

    private fun showNotification(title: String, body: String, link: String) {
        val channelId = "ims_notifications"
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "IMS Notifications",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Alerts for keyword matches on the IMS notifications page"
                enableVibration(true)
            }
            nm.createNotificationChannel(channel)
        }

        val intent = if (link.isNotBlank()) {
            Intent(Intent.ACTION_VIEW, Uri.parse(link))
        } else {
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            }
        }
        val flags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val pending = PendingIntent.getActivity(this, Random.nextInt(), intent, flags)

        val notif = NotificationCompat.Builder(this, channelId)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()

        nm.notify(Random.nextInt(), notif)
    }
}
