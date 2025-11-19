import { useState, useEffect } from 'react';
import { Task } from '../types';
import { tasksApi } from '../api/tasks';
import { TaskForm } from '../components/TaskForm';
import { TaskList } from '../components/TaskList';
import { NotificationSettings } from '../components/NotificationSettings';

export const Dashboard: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadTasks();
  }, []);

  const loadTasks = async () => {
    try {
      setIsLoading(true);
      // 今日から1週間後までの課題を取得
      const now = new Date();
      const weekLater = new Date(now.getTime() + 7 * 24 * 60 * 60 * 1000);
      
      const data = await tasksApi.getAll({
        start_date: now.toISOString(),
        end_date: weekLater.toISOString(),
      });
      setTasks(data);
    } catch (error) {
      console.error('課題の取得に失敗しました:', error);
      alert('課題の取得に失敗しました');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <div style={{ padding: '2rem', textAlign: 'center' }}>読み込み中...</div>;
  }

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem' }}>
      <h1 style={{ marginBottom: '2rem' }}>UniPA Reminder App - ダッシュボード</h1>
      
      <NotificationSettings />
      
      <TaskForm onTaskCreated={loadTasks} />
      
      <TaskList tasks={tasks} onTaskUpdated={loadTasks} />
    </div>
  );
};

