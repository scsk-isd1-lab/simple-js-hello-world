// Hello World メッセージをコンソールに出力する関数
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

function displayUserData(user) {
  console.log(`Name: ${user.name}, Email: ${user.email}`);
}

function displayErrorMessage(message) {
  console.error(`エラー: ${message}`);
}

// アプリケーションのエントリーポイント
displayHelloWorld();