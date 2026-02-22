package com.mapv12.dutytracker

import android.content.Context
import android.util.Log
import com.google.android.gms.nearby.Nearby
import com.google.android.gms.nearby.connection.*

class MeshNetworkManager(private val context: Context, private val myUserId: String) {

    private val connectionsClient: ConnectionsClient = Nearby.getConnectionsClient(context)
    private val STRATEGY = Strategy.P2P_STAR // Топология "Звезда" (идеально для раций/трекеров)
    private val SERVICE_ID = "com.mapv12.dutytracker.MESH"

    private val connectedEndpoints = mutableSetOf<String>()

    // Коллбэк для входящих данных от других устройств (без интернета)
    private val payloadCallback = object : PayloadCallback() {
        override fun onPayloadReceived(endpointId: String, payload: Payload) {
            if (payload.type == Payload.Type.BYTES) {
                val dataStr = payload.asBytes()?.let { String(it) }
                Log.d("MeshNetwork", "Получены данные от $endpointId: $dataStr")
                // TODO: Здесь мы будем сохранять чужие координаты в локальную Room БД,
                // чтобы потом UploadWorker отправил их на сервер, когда появится интернет.
            }
        }

        override fun onPayloadTransferUpdate(endpointId: String, update: PayloadTransferUpdate) {}
    }

    // Коллбэк установки соединения
    private val connectionLifecycleCallback = object : ConnectionLifecycleCallback() {
        override fun onConnectionInitiated(endpointId: String, connectionInfo: ConnectionInfo) {
            Log.d("MeshNetwork", "Подключаемся к: ${connectionInfo.endpointName}")
            // Автоматически принимаем соединение (Zero-Touch, без подтверждения на экране)
            connectionsClient.acceptConnection(endpointId, payloadCallback)
        }

        override fun onConnectionResult(endpointId: String, result: ConnectionResolution) {
            if (result.status.isSuccess) {
                Log.d("MeshNetwork", "Соединение с $endpointId установлено!")
                connectedEndpoints.add(endpointId)

                // TODO: При успешном коннекте, если у нас НЕТ интернета,
                // мы скидываем этому устройству наши неотправленные точки.
            }
        }

        override fun onDisconnected(endpointId: String) {
            Log.d("MeshNetwork", "Отключились от $endpointId")
            connectedEndpoints.remove(endpointId)
        }
    }

    // Начинаем "раздавать" себя (Advertising)
    fun startAdvertising() {
        val options = AdvertisingOptions.Builder().setStrategy(STRATEGY).build()
        connectionsClient.startAdvertising(
            myUserId, // Имя конечной точки (используем наш ID)
            SERVICE_ID,
            connectionLifecycleCallback,
            options
        ).addOnSuccessListener {
            Log.d("MeshNetwork", "Advertising запущен (Я в эфире)")
        }.addOnFailureListener {
            Log.e("MeshNetwork", "Ошибка Advertising", it)
        }
    }

    // Начинаем искать коллег поблизости (Discovery)
    fun startDiscovery() {
        val options = DiscoveryOptions.Builder().setStrategy(STRATEGY).build()
        connectionsClient.startDiscovery(
            SERVICE_ID,
            object : EndpointDiscoveryCallback() {
                override fun onEndpointFound(endpointId: String, info: DiscoveredEndpointInfo) {
                    Log.d("MeshNetwork", "Найден коллега: ${info.endpointName}. Пробуем подключиться...")
                    connectionsClient.requestConnection(myUserId, endpointId, connectionLifecycleCallback)
                }

                override fun onEndpointLost(endpointId: String) {
                    Log.d("MeshNetwork", "Коллега пропал с радаров: $endpointId")
                }
            },
            options
        ).addOnSuccessListener {
            Log.d("MeshNetwork", "Discovery запущен (Ищу коллег)")
        }.addOnFailureListener {
            Log.e("MeshNetwork", "Ошибка Discovery", it)
        }
    }

    // Функция отправки пакета другому узлу
    fun sendDataToNetwork(jsonData: String) {
        val payload = Payload.fromBytes(jsonData.toByteArray())
        if (connectedEndpoints.isNotEmpty()) {
            // Отправляем всем подключенным в Mesh-сети
            connectionsClient.sendPayload(connectedEndpoints.toList(), payload)
            Log.d("MeshNetwork", "Данные отправлены в Mesh-сеть")
        } else {
            Log.d("MeshNetwork", "Нет подключенных коллег для отправки")
        }
    }

    // Остановка всех сетевых операций
    fun stopAll() {
        connectionsClient.stopAdvertising()
        connectionsClient.stopDiscovery()
        connectionsClient.stopAllEndpoints()
        connectedEndpoints.clear()
        Log.d("MeshNetwork", "Mesh-сеть остановлена")
    }
}