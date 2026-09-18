// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::net::TcpStream;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_shell::ShellExt;

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
        .plugin(tauri_plugin_updater::Builder::new().build())
        .setup(|app| {
            let handle = app.handle().clone();

            // 后台检查更新：不阻塞启动，有新版本时下载并安装（下次启动生效）
            let update_handle = handle.clone();
            tauri::async_runtime::spawn(async move {
                check_for_update(update_handle).await;
            });

            // 启动内嵌的 Python 后端（sidecar：backend-x86_64-pc-windows-msvc.exe）
            if is_port_in_use(8000) {
                println!("[Jingent] Port 8000 in use, skip backend sidecar");
            } else {
                match handle.shell().sidecar("backend") {
                    Ok(cmd) => {
                        match cmd.spawn() {
                    Ok((mut rx, _child)) => {
                        println!("[Jingent] backend sidecar started");
                        // drain sidecar stdout/stderr，防止管道缓冲区写满后 backend hang
                        tauri::async_runtime::spawn(async move {
                            use tauri_plugin_shell::process::CommandEvent;
                            while let Some(event) = rx.recv().await {
                                match event {
                                    CommandEvent::Stdout(line) => {
                                        print!("[backend] {}", String::from_utf8_lossy(&line));
                                    }
                                    CommandEvent::Stderr(line) => {
                                        eprint!("[backend] {}", String::from_utf8_lossy(&line));
                                    }
                                    CommandEvent::Terminated(payload) => {
                                        eprintln!(
                                            "[backend] sidecar exited (code={})",
                                            payload.code.unwrap_or(-1)
                                        );
                                        break;
                                    }
                                    _ => {}
                                }
                            }
                        });
                    }
                            Err(e) => {
                                eprintln!("[Jingent] sidecar spawn failed: {}", e);
                            }
                        }
                    }
                    Err(e) => {
                        eprintln!("[Jingent] sidecar not found: {}", e);
                    }
                }
            }

            // 等待后端就绪后导航到 Jinclaw 页面
            std::thread::spawn(move || {
                for _ in 0..40 {
                    if is_port_in_use(8000) { break; }
                    std::thread::sleep(Duration::from_millis(500));
                }
                std::thread::sleep(Duration::from_millis(500));
                if let Some(window) = handle.get_webview_window("main") {
                    println!("[Jingent] navigate to jinclaw");
                    let _ = window.eval(
                        "window.location.replace('http://127.0.0.1:8000/jinclaw?is_desktop=1')"
                    );
                }
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![is_desktop])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

#[tauri::command]
fn is_desktop() -> bool { true }

/// 后台检查并安装更新。失败只打日志，绝不影响正常启动。
async fn check_for_update(app: tauri::AppHandle) {
    use tauri_plugin_updater::UpdaterExt;

    let updater = match app.updater() {
        Ok(u) => u,
        Err(e) => {
            println!("[Jingent] updater unavailable: {}", e);
            return;
        }
    };

    match updater.check().await {
        Ok(Some(update)) => {
            println!(
                "[Jingent] update available: {} -> {}",
                update.current_version, update.version
            );
            match update.download_and_install(|_chunk, _total| {}, || {}).await {
                Ok(_) => println!("[Jingent] update installed; will apply on next launch"),
                Err(e) => eprintln!("[Jingent] update install failed: {}", e),
            }
        }
        Ok(None) => println!("[Jingent] already up to date"),
        Err(e) => println!("[Jingent] update check failed (offline?): {}", e),
    }
}
