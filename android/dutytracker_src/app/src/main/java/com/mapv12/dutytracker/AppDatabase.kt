package com.mapv12.dutytracker

import androidx.room.Database
import androidx.room.RoomDatabase
import com.mapv12.dutytracker.scanner.CameraEntity
import com.mapv12.dutytracker.scanner.CameraDao
import com.mapv12.dutytracker.scanner.wifi.WifiNetworkEntity
import com.mapv12.dutytracker.scanner.wifi.WifiNetworkDao

@Database(
    entities = [
        TrackPointEntity::class,
        EventJournalEntity::class,
        ChatMessageEntity::class,
        CameraEntity::class,
        WifiNetworkEntity::class    // добавлена новая сущность
    ],
    version = 7,                    // увеличь версию с 6 до 7
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun trackPointDao(): TrackPointDao
    abstract fun eventJournalDao(): EventJournalDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun cameraDao(): CameraDao
    abstract fun wifiNetworkDao(): WifiNetworkDao    // новый DAO
}
