// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::{Command, Child};
use std::sync::Mutex;
use std::net::TcpStream;
use std::time::Duration;
use tauri::Manager;

struct AppState {
    python_process: Mutex<Option<Child>>,
}

fn is_port_in_use(port: u16) -> bool {
    TcpStream::connect_timeout(
        &std::net::SocketAddr::from(([127, 0, 0, 1], port)),
        Duration::from_millis(500),
    ).is_ok()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_os::init())
        .manage(AppState {
            python_process: Mutex::new(None),
        })
        .setup(|app| {
            let project_root = if cfg!(debug_assertions) {
                let manifest_dir = std::env::var("CARGO_MANIFEST_DIR")
                    .unwrap_or_else(|_| ".".to_string());
                std::path::PathBuf::from(&manifest_dir)
                    .parent()
                    .unwrap_or_else(|| std::path::Path::new("."))
                    .to_path_buf()
            } else {
                std::env::current_exe()
                    .unwrap()
                    .parent()
                    .unwrap()
                    .to_path_buf()
            };

            let python_path = if cfg!(debug_assertions) {
                project_root
                    .join(".venv")
                    .join("Scripts")
                    .join("python.exe")
                    .to_string_lossy()
                    .to_string()
            } else {
                "python".to_string()
            };

            println!("[Jingent] Python: {}", python_path);
            println!("[Jingent] Cwd:    {}", project_root.display());

            if is_port_in_use(8000) {
                println!("[Jingent] Port 8000 in use, skip Python backend start");
            } else {
                let app_handle = app.handle().clone();
                std::thread::spawn(move || {
                    match Command::new(&python_path)
                        .arg("main.py")
                        .current_dir(&project_root)
                        .spawn()
                    {
                        Ok(child) => {
                            let state = app_handle.state::<AppState>();
                            *state.python_process.lock().unwrap() = Some(child);
                            println!("[Jingent] Python backend started");
                        }
                        Err(e) => {
                            eprintln!("[Jingent] Failed to start Python: {}", e);
                        }
                    }
                });
            }

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![is_desktop])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
fn is_desktop() -> bool { true }

impl Drop for AppState {
    fn drop(&mut self) {
        if let Some(mut child) = self.python_process.lock().unwrap().take() {
            let _ = child.kill();
        }
    }
}
