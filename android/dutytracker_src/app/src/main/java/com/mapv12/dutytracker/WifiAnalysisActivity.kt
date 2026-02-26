package com.mapv12.dutytracker

import android.app.Activity
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.provider.OpenableColumns
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.mapv12.dutytracker.scanner.wifi.WifiAuditResult
import com.mapv12.dutytracker.scanner.wifi.WifiNetworkEntity
import com.mapv12.dutytracker.scanner.wifi.WifiSecurityAuditClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import com.mapv12.dutytracker.scanner.wifi.TaskProgressListener
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.WebSocket
import kotlinx.coroutines.delay
import org.json.JSONObject
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

class WifiAnalysisActivity : AppCompatActivity() {

    companion object {
        private const val REQUEST_CODE_PICK_FILE = 1001
    }

    private lateinit var recycler: RecyclerView
    private lateinit var btnTestSecurity: Button
    private lateinit var btnImportHandshake: Button
    private val adapter = WifiNetworkSelectAdapter()
    private var progressDialog: AlertDialog? = null
    private var progressWebSocket: WebSocket? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_wifi_analysis)

        recycler = findViewById(R.id.recycler_wifi_networks)
        btnTestSecurity = findViewById(R.id.btnTestSecurity)
        btnImportHandshake = findViewById(R.id.btnImportHandshake)

        recycler.layoutManager = LinearLayoutManager(this)
        recycler.adapter = adapter

        lifecycleScope.launch {
            val list = App.db.wifiNetworkDao().getAllNetworks().first()
            adapter.submitList(list)
        }


        btnImportHandshake.setOnClickListener {
            val intent = Intent(Intent.ACTION_GET_CONTENT).apply {
                type = "*/*"
                addCategory(Intent.CATEGORY_OPENABLE)
            }
            @Suppress("DEPRECATION")
            startActivityForResult(intent, REQUEST_CODE_PICK_FILE)
        }

        btnTestSecurity.setOnClickListener {
            val selectedNetwork = adapter.getSelectedNetwork()
            if (selectedNetwork == null) {
                showAlert("Сеть не выбрана", "Выберите сеть из списка для проверки")
                return@setOnClickListener
            }

            lifecycleScope.launch {
                btnTestSecurity.isEnabled = false
                btnTestSecurity.text = "Проверка..."

                val client = WifiSecurityAuditClient(this@WifiAnalysisActivity)
                val start = client.requestAudit(selectedNetwork)

                if (start == null) {
                    showAlert("Ошибка", "Не удалось запустить проверку безопасности")
                    btnTestSecurity.isEnabled = true
                    btnTestSecurity.text = "Тест безопасности выбранной сети"
                    return@launch
                }

                val taskId = start.taskId
                showProgressDialog(taskId, start.estimatedTime)

                start.wsToken?.let { token ->
                    progressWebSocket = client.connectToTaskProgress(token, TaskProgressListener { current, total ->
                        runOnUiThread {
                            val safeTotal = if (total <= 0) 100 else total
                            val percent = ((current.toFloat() / safeTotal.toFloat()) * 100f).toInt().coerceIn(0, 100)
                            btnTestSecurity.text = "Проверка... ${percent}%"
                            updateProgressDialog(percent, start.estimatedTime)
                        }
                    })
                }

                var result: WifiAuditResult? = null
                for (attempt in 0 until 90) {
                    delay(2000)
                    val status = client.getAuditStatus(taskId)
                    if (status != null) {
                        val safeProgress = status.progress.coerceIn(0, 100)
                        val eta = status.estimatedTimeSeconds
                        btnTestSecurity.text = "Проверка... ${safeProgress}%"
                        updateProgressDialog(safeProgress, eta)

                        if (status.status.equals("completed", ignoreCase = true) || safeProgress >= 100) {
                            val finalResult = client.getAuditResult(taskId)
                            result = finalResult ?: WifiAuditResult(
                                bssid = selectedNetwork.bssid,
                                isVulnerable = status.result?.isVulnerable ?: false,
                                vulnerabilityType = status.result?.vulnerabilityType,
                                foundPassword = status.result?.foundPassword,
                                report = status.result?.serverReport,
                                status = status.status,
                                progress = status.progress,
                                estimatedTime = status.estimatedTimeSeconds,
                                message = status.result?.serverReport
                            )
                            break
                        } else if (status.status.equals("failed", ignoreCase = true)) {
                            dismissProgressDialog()
                            showAlert("Ошибка", "Проверка завершилась с ошибкой")
                            break
                        }
                    }
                }

                if (result != null) {
                    dismissProgressDialog()
                    showResultDialog(result)
                    updateNetworkInDb(result)
                } else {
                    dismissProgressDialog()
                    showAlert("Проверка не завершена", "Результат пока недоступен, попробуйте позже")
                }

                progressWebSocket?.close(1000, "Task flow finished")
                progressWebSocket = null
                btnTestSecurity.isEnabled = true
                btnTestSecurity.text = "Тест безопасности выбранной сети"
            }
        }
    }


    @Suppress("DEPRECATION")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == REQUEST_CODE_PICK_FILE && resultCode == Activity.RESULT_OK) {
            data?.data?.let { uri ->
                uploadHandshakeFile(uri)
            }
        }
    }

    private fun uploadHandshakeFile(uri: Uri) {
        val selectedNetwork = adapter.getSelectedNetwork()
        if (selectedNetwork == null) {
            showAlert("Импорт handshake", "Сначала выберите сеть для заполнения BSSID/ESSID")
            return
        }

        lifecycleScope.launch {
            try {
                val mimeType = contentResolver.getType(uri) ?: "application/octet-stream"
                val fileName = getFileName(uri) ?: "handshake.cap"
                val bytes = withContext(Dispatchers.IO) {
                    contentResolver.openInputStream(uri)?.use { it.readBytes() }
                } ?: byteArrayOf()

                if (bytes.isEmpty()) {
                    showAlert("Ошибка", "Не удалось прочитать выбранный файл")
                    return@launch
                }

                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("bssid", selectedNetwork.bssid)
                    .addFormDataPart("essid", selectedNetwork.ssid)
                    .addFormDataPart("security_type", selectedNetwork.securityType)
                    .addFormDataPart("client_id", getClientId())
                    .addFormDataPart(
                        "file",
                        fileName,
                        bytes.toRequestBody(mimeType.toMediaTypeOrNull())
                    )
                    .build()

                val baseUrl = Config.getBaseUrl(this@WifiAnalysisActivity).trim().trimEnd('/')
                val requestBuilder = Request.Builder()
                    .url("$baseUrl/api/video/handshake/upload")
                    .post(requestBody)

                SecureStores.getAuditApiKey(this@WifiAnalysisActivity)
                    ?.takeIf { it.isNotBlank() }
                    ?.let { requestBuilder.addHeader("X-API-Key", it) }

                val responseBody = withContext(Dispatchers.IO) {
                    OkHttpClient().newCall(requestBuilder.build()).execute().use { response ->
                        if (!response.isSuccessful) {
                            return@use "ERR:${response.code}"
                        }
                        response.body?.string().orEmpty()
                    }
                }

                if (responseBody.startsWith("ERR:")) {
                    showAlert("Ошибка загрузки", "Ошибка загрузки: ${responseBody.removePrefix("ERR:")}")
                    return@launch
                }

                val json = JSONObject(responseBody)
                val taskId = json.optString("taskId")
                if (taskId.isBlank()) {
                    showAlert("Ошибка", "Сервер вернул некорректный ответ")
                    return@launch
                }

                showAlert("Импорт handshake", "Файл загружен, анализ начат (taskId: $taskId)")
            } catch (e: Exception) {
                showAlert("Ошибка", "Ошибка: ${e.message}")
            }
        }
    }

    private fun getClientId(): String {
        return SecureStores.getDeviceToken(this) ?: "android-client"
    }

    private fun getFileName(uri: Uri): String? {
        var result: String? = null
        if (uri.scheme == "content") {
            val cursor: Cursor? = contentResolver.query(uri, null, null, null, null)
            cursor?.use {
                if (it.moveToFirst()) {
                    val displayNameIndex = it.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (displayNameIndex != -1) {
                        result = it.getString(displayNameIndex)
                    }
                }
            }
        }
        if (result == null) {
            result = uri.path
            val cut = result?.lastIndexOf('/')
            if (cut != null && cut != -1) {
                result = result?.substring(cut + 1)
            }
        }
        return result
    }

    override fun onDestroy() {
        progressWebSocket?.close(1000, "Activity destroyed")
        progressWebSocket = null
        dismissProgressDialog()
        super.onDestroy()
    }

    private fun showProgressDialog(taskId: String, estimatedTime: Int) {
        val eta = if (estimatedTime > 0) estimatedTime else 300
        progressDialog?.dismiss()
        progressDialog = AlertDialog.Builder(this)
            .setTitle("Проверка запущена")
            .setMessage("Task: $taskId\nПрогресс: 0%\nОценочное время: ${eta} сек")
            .setCancelable(false)
            .setNegativeButton("Скрыть", null)
            .show()
    }

    private fun updateProgressDialog(progress: Int, estimatedTime: Int) {
        val eta = if (estimatedTime > 0) estimatedTime else 300
        progressDialog?.setMessage("Прогресс: ${progress}%\nОценочное время: ${eta} сек")
    }

    private fun dismissProgressDialog() {
        progressDialog?.dismiss()
        progressDialog = null
    }

    private suspend fun updateNetworkInDb(result: WifiAuditResult) {
        val wifiDao = App.db.wifiNetworkDao()
        val existing = wifiDao.getNetworkByBssid(result.bssid)
        if (existing != null) {
            val updated = existing.copy(
                isVulnerable = result.isVulnerable,
                vulnerabilityType = result.vulnerabilityType,
                testedPassword = result.foundPassword,
                lastTested = System.currentTimeMillis()
            )
            wifiDao.insertNetwork(updated)
        }
    }

    private fun showResultDialog(result: WifiAuditResult) {
        val msg = buildString {
            append("BSSID: ${result.bssid}\n")
            append("Уязвима: ${if (result.isVulnerable) "Да" else "Нет"}\n")
            if (!result.vulnerabilityType.isNullOrBlank()) append("Тип: ${result.vulnerabilityType}\n")
            if (!result.foundPassword.isNullOrBlank()) append("Пароль: ${result.foundPassword}\n")
            if (!result.message.isNullOrBlank()) append("Сообщение: ${result.message}\n")
            if (result.estimatedTime > 0) append("Оценка: ${result.estimatedTime} сек\n")
            append("Прогресс: ${result.progress}%\n")
            if (!result.report.isNullOrBlank()) append("Отчёт: ${result.report}")
        }.trim()
        showAlert("Результат проверки", msg)
    }

    private fun showAlert(title: String, message: String) {
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(message)
            .setPositiveButton("OK", null)
            .show()
    }
}

private class WifiNetworkSelectAdapter : RecyclerView.Adapter<WifiNetworkSelectAdapter.VH>() {
    private val items = mutableListOf<WifiNetworkEntity>()
    private var selectedPos = RecyclerView.NO_POSITION

    fun submitList(newItems: List<WifiNetworkEntity>) {
        items.clear()
        items.addAll(newItems)
        selectedPos = RecyclerView.NO_POSITION
        notifyDataSetChanged()
    }

    fun getSelectedNetwork(): WifiNetworkEntity? =
        if (selectedPos in items.indices) items[selectedPos] else null

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        val view = LayoutInflater.from(parent.context)
            .inflate(R.layout.item_wifi_network, parent, false)
        return VH(view)
    }

    override fun onBindViewHolder(holder: VH, position: Int) {
        holder.bind(items[position], position == selectedPos)
        holder.itemView.setOnClickListener {
            val prev = selectedPos
            selectedPos = holder.bindingAdapterPosition
            if (prev != RecyclerView.NO_POSITION) notifyItemChanged(prev)
            notifyItemChanged(selectedPos)
        }
    }

    override fun getItemCount(): Int = items.size

    class VH(itemView: View) : RecyclerView.ViewHolder(itemView) {
        private val tvTitle: TextView = itemView.findViewById(R.id.tv_wifi_title)
        private val tvSubtitle: TextView = itemView.findViewById(R.id.tv_wifi_subtitle)

        fun bind(item: WifiNetworkEntity, isSelected: Boolean) {
            tvTitle.text = item.ssid.ifBlank { "<hidden>" }
            tvSubtitle.text = "${item.bssid} · ${item.securityType}"
            itemView.isSelected = isSelected
            itemView.alpha = if (isSelected) 1f else 0.85f
        }
    }
}
