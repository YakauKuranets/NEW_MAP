use axum::{routing::post, Json, Router, extract::State};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
// Удален неиспользуемый Mutex
use redis::AsyncCommands;

// Структура, которую присылает Android-приложение
#[derive(Deserialize, Serialize, Debug)]
struct TelemetryPayload {
    user_id: String,
    lat: f64,
    lon: f64,
    accuracy_m: Option<f64>,
    unit_label: Option<String>,
}

// Структура для отправки в нашу WebSocket-шину (чтобы React-карта поняла)
#[derive(Serialize)]
struct WsMessage {
    event: String,
    data: TelemetryPayload,
}

// Состояние приложения (держит пул подключений к Redis)
struct AppState {
    redis_client: redis::Client,
}

// Сверхбыстрый эндпоинт приема координат
async fn handle_telemetry(
    State(state): State<Arc<AppState>>,
    Json(payload): Json<TelemetryPayload>,
) -> &'static str {
    
    // 1. Упаковываем в нужный формат для фронтенда
    let ws_msg = WsMessage {
        event: "duty_location_update".to_string(), // Это событие ждет карта
        data: payload,
    };
    
    // 2. Мгновенный проброс в шину Redis (Pub/Sub)
    if let Ok(mut con) = state.redis_client.get_async_connection().await {
        if let Ok(msg_str) = serde_json::to_string(&ws_msg) {
            // Публикуем в канал 'map_updates', который слушает твой Python app/sockets.py
            let _: Result<(), _> = con.publish("map_updates", msg_str).await;
        }
    }

    // 3. Возвращаем 200 OK за доли миллисекунды, чтобы телефон не ждал
    "OK" 
}

#[tokio::main]
async fn main() {
    // Подключаемся к Redis (в продакшене брать из ENV)
    let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1/".to_string());
    
    // Инициализируем клиента
    let client = redis::Client::open(redis_url).expect("❌ Не удалось подключиться к Redis");
    
    let state = Arc::new(AppState { redis_client: client });

    // Настраиваем роутер Axum
    let app = Router::new()
        .route("/api/duty/telemetry/fast", post(handle_telemetry))
        .with_state(state);

    // Запускаем сервер на порту 3000
    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await.unwrap();
    println!("🚀 Rust Telemetry Node запущена на порту 3000!");
    axum::serve(listener, app).await.unwrap();
}