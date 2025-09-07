/**
 * Hello World メッセージをコンソールに出力し、APIリクエストを開始する
 * @public
 * @returns {void}
 */
function displayHelloWorld() {
  console.log('Hello, World!');
  fetchUserData();
}

/**
 * APIからユーザーデータを取得する
 * @public
 * @param {number} userId - 取得するユーザーのID（デフォルト: 1）
 * @returns {Promise<Object|null>} ユーザーデータまたはnull
 * @throws {Error} APIリクエスト失敗時にエラーをスロー（内部でキャッチされる）
 */
async function fetchUserData(userId = 1) {
  const apiUrl = `https://jsonplaceholder.typicode.com/users/${userId}`;
  
  try {
    const response = await fetch(apiUrl);
    
    // HTTP エラーハンドリング
    if (!response.ok) {
      throw new Error(`APIエラー: ${response.status} ${response.statusText}`);
    }
    
    const userData = await response.json();
    displayUserInfo(userData);
    return userData;
  } catch (error) {
    handleApiError(error);
    return null;
  }
}

/**
 * APIエラーを処理し、ユーザーに通知する
 * @param {Error} error - 発生したエラー
 * @private
 * @returns {void}
 */
function handleApiError(error) {
  console.error('データ取得中にエラーが発生しました:', error.message);
  // DOMがある環境では、ユーザーに表示するエラーメッセージを追加
  if (typeof document !== 'undefined') {
    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.textContent = `データ取得に失敗しました: ${error.message}`;
    document.body.appendChild(errorElement);
  }
}

/**
 * ユーザー情報を表示する
 * @param {Object} user - ユーザーデータ
 * @param {string} user.name - ユーザーの名前
 * @param {string} user.email - ユーザーのメールアドレス
 * @private
 * @returns {void}
 */
function displayUserInfo(user) {
  console.log(`ユーザー情報: ${user.name} (${user.email})`);
}

// アプリケーションのエントリーポイント
displayHelloWorld();