# ff_pdtv

FlaskFarm (SJVA) Plugin for PandaTV (팬더TV)

팬더TV 실시간 방송 목록 수집, M3U 플레이리스트 생성 및 스트리밍 재생 지원 플러그인입니다.

## 저장소 (Repository)
- GitHub: [https://github.com/fromhd/ff_pdtv](https://github.com/fromhd/ff_pdtv)
- 원출처 (Original Repository): [https://github.com/ssagajikorea/ff_pdtv](https://github.com/ssagajikorea/ff_pdtv) (by ssagajikorea)

## 주요 기능
- 최신 PandaTV REST API 연동
- 실시간 방송 채널 목록 자동 조회
- M3U 플레이리스트 및 Plex용 YAML 생성
- AWS IVS HLS M3U8 스트림 실시간 URL 발급 및 재생 (Redirect, Direct, Proxy 모드 지원)
- Amazon IVS Origin/Referer 헤더 무결성 지원으로 403 Forbidden 오류 완벽 방지
- 회원 로그인 인증 지원 (성인 방송 시청)
- 프록시 (Proxy1 / Proxy2) 설정 지원 (해외 및 클라우드 서버 대응)

## 설치 방법 (FlaskFarm)
1. FlaskFarm 관리자 페이지 접속
2. **플러그인 > 플러그인 설치 (Git)** 메뉴 이동
3. Git 주소에 `https://github.com/fromhd/ff_pdtv` 입력 후 설치
4. 플러그인 목록에서 `ff_pdtv` 활성화