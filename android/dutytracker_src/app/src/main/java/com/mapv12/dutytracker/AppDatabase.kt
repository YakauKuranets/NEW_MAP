package com.mapv12.dutytracker

import androidx.room.Database
import androidx.room.RoomDatabase
import com.mapv12.dutytracker.scanner.CameraDao
import com.mapv12.dutytracker.scanner.CameraEntity
import com.mapv12.dutytracker.scanner.wifi.WifiNetworkDao
import com.mapv12.dutytracker.scanner.wifi.WifiNetworkEntity

@Database(
    entities = [
        TrackPointEntity::class,
        EventJournalEntity::class,
        ChatMessageEntity::class,
        CameraEntity::class,
        WifiNetworkEntity::class
    ],
    version = 9,
    exportSchema = false
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun trackPointDao(): TrackPointDao
    abstract fun eventJournalDao(): EventJournalDao
    abstract fun chatMessageDao(): ChatMessageDao
    abstract fun cameraDao(): CameraDao   // новый DAO
    abstract fun wifiNetworkDao(): WifiNetworkDao
}
