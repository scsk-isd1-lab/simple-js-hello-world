/**
 * Hello World メッセージをコンソールに出力し、ユーザーデータ取得を開始する関数
 * アプリケーションの主要なエントリーポイント関数として機能する
 * 
 * @returns {void}
 * @example displayHelloWorld();
 */
function displayHelloWorld() {
  console.log('Hello, World!');
  fetchUserData();
}

/**
 * 外部APIからユーザーデータを取得する関数
 * @async
 * @param {number} [userId=1] - 取得するユーザーのID
 * @returns {Promise<Object|null>} 成功時はユーザーデータ、失敗時はnull
 */
async function fetchUserData(userId = 1) {
  const apiUrl = `https://jsonplaceholder.typicode.com/users/${userId}`;
  
  try {
    // APIリクエストの開始をログ
    console.log(`Fetching user data from: ${apiUrl}`);
    
    const response = await fetch(apiUrl);
    
    // レスポンスステータスコードの確認
    if (!response.ok) {
      throw new Error(`API request failed with status: ${response.status}`);
    }
    
    const userData = await response.json();
    console.log('User data retrieved successfully:', userData);
    
    // 取得したデータを表示（実際のアプリでは適切なDOM操作などで表示）
    displayUserData(userData);
    
    return userData;
  } catch (error) {
    // エラーハンドリング
    console.error('Error fetching user data:', error.message);
    displayErrorMessage(`ユーザーデータの取得に失敗しました: ${error.message}`);
    return null;
  }
}

/**
 * ユーザーデータをコンソールに表示する関数
 * 実際のアプリケーションではDOM要素に表示するように拡張可能
 * 
 * @param {Object} user - 表示するユーザー情報
 * @param {string} user.name - ユーザーの名前
 * @param {string} user.email - ユーザーのメールアドレス
 * @returns {void}
 */
function displayUserData(user) {
  console.log(`Name: ${user.name}, Email: ${user.email}`);
}

/**
 * エラーメッセージをコンソールに表示する関数
 * 実際のアプリケーションではUI上に適切に表示するように拡張可能
 * 
 * @param {string} message - 表示するエラーメッセージ
 * @returns {void}
 */
function displayErrorMessage(message) {
  console.error(`エラー: ${message}`);
}

/**
 * アプリケーションの起動
 * ページロード時にアプリケーションを初期化する
 * 
 * 将来的にはより複雑な初期化ロジックに拡張可能
 */
displayHelloWorld();

// Node.jsでモジュールとしてエクスポート（必要に応じて）
// module.exports = { displayHelloWorld, fetchUserData, displayUserData, displayErrorMessage };