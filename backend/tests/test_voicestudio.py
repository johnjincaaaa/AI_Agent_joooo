"""
先拉起voicestudio的脚本启动服务构建桥tts，然后运行测试脚本
 完整测试脚本，一次性覆盖 **健康检查、音色列表、TTS 合成、音色克隆、语音转文字、文字描述音色** 全部接口
"""

from backend.app.services.tts_client import (
    check_health,
    list_voices,
    synthesize,
    clone_voice,
    transcribe,
    design_voice,
    describe_voice
)

def test_synthesize_cloned():
    print("\n===== 使用克隆音色TTS =====")
    ok, audio_bytes, err = synthesize(
        "你好，我是刚刚克隆出来的声音，测试一下音色效果。",
        voice="5bd91bb4",
        fmt="wav",
        speed=1.0
    )
    assert ok, f"合成失败：{err}"
    with open("test_cloned_voice.wav", "wb") as f:
        f.write(audio_bytes)
    print("✅ 克隆音色音频保存 test_cloned_voice.wav")



def test_voice_studio_health():
    """1. 健康检查"""
    res = check_health()
    print("\n===== 健康检查 =====")
    print(res)
    assert res["ok"] is True

def test_list_voices():
    """2. 获取音色列表"""
    print("\n===== 音色列表 =====")
    voices = list_voices()
    print(voices)
    assert isinstance(voices, list)

def test_synthesize():
    """3. TTS文本转语音"""
    print("\n===== TTS合成 =====")
    ok, audio_bytes, err = synthesize(
        "你好，这是OmniVoice语音测试，语速正常。",
        voice="default",
        fmt="wav",
        speed=1.0
    )
    assert ok, f"合成失败：{err}"
    assert len(audio_bytes) > 1000
    with open("test_synthesize.wav", "wb") as f:
        f.write(audio_bytes)
    print("✅ TTS音频保存 test_synthesize.wav")

def test_clone_voice():
    """4. 音色克隆（需要你准备一段参考wav音频）"""
    print("\n===== 音色克隆 =====")
    # 【这里改成你自己的参考音频路径】
    ref_path = "ref.wav"
    with open(ref_path, "rb") as f:
        ref_audio = f.read()
    ok, profile, err = clone_voice(
        name="克隆音色01",
        audio=ref_audio,
        filename="ref.wav",
        ref_text="大家好，我是用来克隆声音的参考录音",
        language="zh"
    )
    assert ok, f"克隆失败：{err}"
    print("✅ 克隆音色信息：", profile)
    # 拿到克隆出来的voice_id，后续synthesize可以直接用
    return profile["id"]

def test_transcribe():
    """5. STT语音转文字（用上面生成的wav测试）"""
    print("\n===== STT语音转文字 =====")
    with open("test_synthesize.wav", "rb") as f:
        audio_data = f.read()
    ok, text, err = transcribe(
        audio_bytes=audio_data,
        filename="test_synthesize.wav"
    )
    assert ok, f"识别失败：{err}"
    print(f"✅ STT识别结果：{text}")

def test_describe_voice():
    """6. 文字描述音色属性（不保存）"""
    print("\n===== 音色描述解析 =====")
    ok, attrs, err = describe_voice("温柔年轻女声，语速平缓，普通话")
    assert ok, f"解析失败：{err}"
    print("✅ 音色属性：", attrs)

def test_design_voice():
    """7. 根据文字直接生成音色profile"""
    print("\n===== 文字生成音色 =====")
    ok, profile, err = design_voice(
        description="低沉磁性男生，稳重",
        sample_text="你好，很高兴认识你",
        language="zh"
    )
    assert ok, f"生成音色失败：{err}"
    print("✅ 设计音色profile：", profile)
