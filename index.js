// ブラウザでDOMが読み込まれた後に実行される関数
document.addEventListener('DOMContentLoaded', () => {
  // Hello World メッセージをコンソールに出力
  console.log('Hello, World!');
  
  // Hello World メッセージを画面に表示
  const messageElement = document.getElementById('message');
  if (messageElement) {
    messageElement.textContent = 'Hello, World!';
  }
});
