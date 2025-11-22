import { Task } from '../types';
import { tasksApi } from '../api/tasks';

interface TaskListProps {
  tasks: Task[];
  onTaskUpdated: () => void;
}

export const TaskList: React.FC<TaskListProps> = ({ tasks, onTaskUpdated }) => {
  const handleToggleDone = async (task: Task) => {
    try {
      await tasksApi.update(task.id, { is_done: !task.is_done });
      onTaskUpdated();
    } catch (error) {
      console.error('課題の更新に失敗しました:', error);
      alert('課題の更新に失敗しました');
    }
  };

  const handleDelete = async (taskId: number) => {
    if (!confirm('この課題を削除しますか？')) {
      return;
    }
    try {
      await tasksApi.delete(taskId);
      onTaskUpdated();
    } catch (error) {
      console.error('課題の削除に失敗しました:', error);
      alert('課題の削除に失敗しました');
    }
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (tasks.length === 0) {
    return <p style={{ color: '#666' }}>課題がありません</p>;
  }

  return (
    <div>
      <h2>課題一覧</h2>
      <ul style={{ listStyle: 'none', padding: 0 }}>
        {tasks.map((task) => {
          const isOverdue = !task.is_done && new Date(task.deadline) < new Date();
          return (
            <li
              key={task.id}
              style={{
                marginBottom: '1rem',
                padding: '1rem',
                border: '1px solid #ddd',
                borderRadius: '8px',
                backgroundColor: isOverdue ? '#fff3cd' : task.is_done ? '#d4edda' : 'white',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1 }}>
                  {/* タイトル + チェックボックス */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <input
                      type="checkbox"
                      checked={task.is_done}
                      onChange={() => handleToggleDone(task)}
                    />
                    <h3
                      style={{
                        margin: 0,
                        textDecoration: task.is_done ? 'line-through' : 'none',
                      }}
                    >
                      {task.title}
                    </h3>
                  </div>

                  <p style={{ margin: '0.25rem 0', color: '#666' }}>授業: {task.course_name}</p>
                  <p
                    style={{
                      margin: '0.25rem 0',
                      color: isOverdue ? '#dc3545' : '#666',
                      fontWeight: isOverdue ? 'bold' : 'normal',
                    }}
                  >
                    締切: {formatDateTime(task.deadline)}
                    {isOverdue && ' (期限切れ)'}
                  </p>
                  {task.memo && (
                    <p style={{ margin: '0.25rem 0', color: '#666' }}>メモ: {task.memo}</p>
                  )}
                </div>

                <div>
                  {/* statusをテキスト表示だけに */}
                  <div style={{ marginBottom: '0.5rem', textAlign: 'right', fontSize: '0.9rem', color: '#555' }}>
                    {task.is_done ? '✅ 完了済み' : '⏳ 未完了'}
                  </div>
                  <button
                    onClick={() => handleDelete(task.id)}
                    style={{
                      padding: '0.5rem 1rem',
                      backgroundColor: '#dc3545',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                    }}
                  >
                    削除
                  </button>
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
};
