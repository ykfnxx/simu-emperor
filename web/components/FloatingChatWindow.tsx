'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import type {
  CharacterId,
  CharacterPublicView,
  GameplayConversation,
  GameplayCourtView,
  GameplayMessage,
  OfficeId,
  OfficeView
} from '../../src/contracts/gameplay';
import {
  getAppointedCharacters,
  getCharacterPortraitClass,
  getConversationCharacterIds
} from '../client-api';

export interface FloatingChatWindowProps {
  open: boolean;
  courtView: GameplayCourtView;
  characterById: ReadonlyMap<CharacterId, CharacterPublicView>;
  conversations: GameplayConversation[];
  activeConversationId: string | null;
  selectedContactCharacterId: CharacterId | null;
  activeMessages: GameplayMessage[];
  messagesLoading: boolean;
  chatBusy: boolean;
  chatError: string | null;
  isHistoryView: boolean;
  draftText: string;
  groupMentions: CharacterId[];
  onClose: () => void;
  onSelectCharacterContact: (characterId: CharacterId) => void;
  onSelectConversation: (conversationId: string) => void;
  onRefreshConversation: () => void;
  onChangeDraft: (text: string) => void;
  onToggleGroupMention: (characterId: CharacterId) => void;
  onSendMessage: () => void;
  onCreateGroupConversation: (
    title: string,
    characterIds: CharacterId[]
  ) => Promise<void> | void;
  onOpenBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onHoverBiography?: (
    characterId: CharacterId,
    anchorEl?: HTMLElement | null
  ) => void;
  onLeaveBiography?: () => void;
}

function useModalDialogFocus(
  isOpen: boolean,
  dialogRef: React.RefObject<HTMLElement | null>
) {
  const triggerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    triggerRef.current = document.activeElement as HTMLElement | null;
    const dialogEl = dialogRef.current;
    if (dialogEl) {
      const firstFocusable = dialogEl.querySelector<HTMLElement>(
        'input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(:disabled)'
      );
      (firstFocusable ?? dialogEl).focus();
    }
    return () => {
      if (triggerRef.current && document.body.contains(triggerRef.current)) {
        triggerRef.current.focus();
      }
    };
  }, [isOpen, dialogRef]);
}

export const FloatingChatWindow: React.FC<FloatingChatWindowProps> = ({
  open,
  courtView,
  characterById,
  conversations,
  activeConversationId,
  selectedContactCharacterId,
  activeMessages,
  messagesLoading,
  chatBusy,
  chatError,
  isHistoryView,
  draftText,
  groupMentions,
  onClose,
  onSelectCharacterContact,
  onSelectConversation,
  onRefreshConversation,
  onChangeDraft,
  onToggleGroupMention,
  onSendMessage,
  onCreateGroupConversation,
  onOpenBiography,
  onHoverBiography,
  onLeaveBiography
}) => {
  const [membersPopupOpen, setMembersPopupOpen] = useState(false);
  const [groupCreateOpen, setGroupCreateOpen] = useState(false);
  const [groupTitle, setGroupTitle] = useState('三省钱粮会商');
  const [selectedGroupMemberIds, setSelectedGroupMemberIds] = useState<CharacterId[]>([]);

  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const membersDialogRef = useRef<HTMLElement | null>(null);
  const groupCreateDialogRef = useRef<HTMLElement | null>(null);

  useModalDialogFocus(membersPopupOpen, membersDialogRef);
  useModalDialogFocus(groupCreateOpen, groupCreateDialogRef);

  useEffect(() => {
    if (!membersPopupOpen && !groupCreateOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        e.preventDefault();
        if (membersPopupOpen) {
          setMembersPopupOpen(false);
        } else if (groupCreateOpen) {
          setGroupCreateOpen(false);
        }
      }
    };
    window.addEventListener('keydown', onKeyDown, true);
    return () => window.removeEventListener('keydown', onKeyDown, true);
  }, [membersPopupOpen, groupCreateOpen]);

  const canInteract =
    !isHistoryView && courtView.active_turn.phase !== 'ARCHIVED';

  const activeOfficeByCharacter = useMemo(() => {
    const officeById = new Map<OfficeId, OfficeView>(
      courtView.offices.map((o) => [o.office_id, o])
    );
    const map = new Map<CharacterId, OfficeView>();
    for (const pv of courtView.provinces) {
      const appt = pv.appointment;
      if (appt) {
        const off = officeById.get(appt.office_id);
        if (off) {
          map.set(appt.character_id, off);
        }
      }
    }
    return map;
  }, [courtView.provinces, courtView.offices]);

  const appointedCharacters = useMemo(
    () => getAppointedCharacters(courtView),
    [courtView]
  );

  useEffect(() => {
    if (groupCreateOpen) {
      setSelectedGroupMemberIds(appointedCharacters.map((c) => c.character_id));
    }
  }, [groupCreateOpen, appointedCharacters]);

  const activeConversation = useMemo(
    () =>
      conversations.find((c) => c.conversation_id === activeConversationId) ??
      null,
    [conversations, activeConversationId]
  );

  const activeCharIds = useMemo(
    () =>
      activeConversation ? getConversationCharacterIds(activeConversation) : [],
    [activeConversation]
  );

  const headerCharacter = useMemo(() => {
    if (activeConversation?.kind === 'dm' && activeCharIds[0]) {
      return characterById.get(activeCharIds[0]) ?? null;
    }
    if (!activeConversation && selectedContactCharacterId) {
      return characterById.get(selectedContactCharacterId) ?? null;
    }
    return null;
  }, [
    activeConversation,
    activeCharIds,
    selectedContactCharacterId,
    characterById
  ]);

  const headerOfficeTitle = useMemo(() => {
    if (!headerCharacter) return '';
    return (
      activeOfficeByCharacter.get(headerCharacter.character_id)?.title ?? '候任'
    );
  }, [headerCharacter, activeOfficeByCharacter]);

  const dmConversationByCharacter = useMemo(() => {
    const map = new Map<CharacterId, GameplayConversation>();
    for (const conv of conversations) {
      if (conv.kind === 'dm') {
        const charId = getConversationCharacterIds(conv)[0];
        if (charId && !map.has(charId)) {
          map.set(charId, conv);
        }
      }
    }
    return map;
  }, [conversations]);

  const groupConversations = useMemo(
    () => conversations.filter((c) => c.kind === 'group'),
    [conversations]
  );

  useEffect(() => {
    if (!open) return;
    const el = messagesContainerRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [open, activeConversationId, activeMessages.length]);

  useEffect(() => {
    if (open && canInteract) {
      inputRef.current?.focus();
    }
  }, [open, activeConversationId, selectedContactCharacterId, canInteract]);

  if (!open) {
    return null;
  }

  const canSendInCurrentView =
    canInteract &&
    (activeConversation !== null || selectedContactCharacterId !== null);

  const handleToggleNewGroupMember = (characterId: CharacterId) => {
    setSelectedGroupMemberIds((prev) =>
      prev.includes(characterId)
        ? prev.filter((id) => id !== characterId)
        : [...prev, characterId]
    );
  };

  const handleConfirmCreateGroup = async () => {
    if (!canInteract || selectedGroupMemberIds.length === 0) return;
    await onCreateGroupConversation(
      groupTitle.trim() || '三省廷议',
      selectedGroupMemberIds
    );
    setGroupCreateOpen(false);
  };

  return (
    <>
      <aside
        className="floating-chat"
        id="floating-chat"
        aria-label="御前密谈"
        data-testid="floating-chat-window"
      >
        <div className="win-bar">
          <div className="win-id">
            {activeConversation?.kind === 'group' ? (
              <div>
                <strong id="chat-person-name">{activeConversation.title}</strong>
                <span id="chat-person-role">{activeCharIds.length}人廷议</span>
              </div>
            ) : headerCharacter ? (
              <>
                <span
                  className={`portrait small ${getCharacterPortraitClass(headerCharacter.character_id)}`}
                  id="chat-portrait"
                  aria-hidden="true"
                />
                <div>
                  <strong id="chat-person-name">{headerCharacter.name}</strong>
                  <span id="chat-person-role">{headerOfficeTitle}</span>
                </div>
              </>
            ) : (
              <div>
                <strong id="chat-person-name">御前密谈</strong>
                <span id="chat-person-role">臣工奏对</span>
              </div>
            )}
          </div>
          <div className="win-actions">
            {activeConversation?.kind === 'group' && (
              <button
                type="button"
                className="win-btn"
                id="chat-members-btn"
                data-testid="chat-members-btn"
                title="廷议成员"
                aria-label="廷议成员"
                onClick={() => setMembersPopupOpen(true)}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle
                    cx="12"
                    cy="12"
                    r="8.5"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                  />
                  <path
                    d="M12 10.2v5.4M12 7.4h.01"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            )}
            <button
              type="button"
              className="win-btn"
              id="chat-refresh-btn"
              data-testid="chat-refresh-btn"
              title="刷新会话"
              aria-label="刷新会话"
              disabled={!activeConversation || messagesLoading}
              onClick={onRefreshConversation}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M3 4v6h6M3.5 15a9 9 0 1 0 2.1-9.4L3 10"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            <button
              type="button"
              className="win-btn"
              id="new-group-chat"
              data-testid="new-group-chat-btn"
              title="新建廷议"
              aria-label="新建廷议"
              disabled={!canInteract}
              onClick={() => setGroupCreateOpen(true)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M12 4v16M4 12h16"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                />
              </svg>
            </button>
            <button
              type="button"
              className="win-btn"
              id="close-chat"
              data-testid="close-chat-btn"
              aria-label="关闭"
              onClick={onClose}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
        </div>

        <div className="chat-contacts" id="chat-contacts">
          {courtView.characters.map((char) => {
            const existingDm = dmConversationByCharacter.get(char.character_id);
            const isActive = existingDm
              ? activeConversationId === existingDm.conversation_id
              : !activeConversationId &&
                selectedContactCharacterId === char.character_id;
            return (
              <button
                key={char.character_id}
                type="button"
                className={`chat-contact ${isActive ? 'active' : ''}`}
                data-chat-select={char.character_id}
                data-testid={`chat-contact-${char.character_id}`}
                onClick={() => {
                  if (existingDm) {
                    onSelectConversation(existingDm.conversation_id);
                  } else {
                    onSelectCharacterContact(char.character_id);
                  }
                }}
              >
                {char.name}
              </button>
            );
          })}
          {groupConversations.map((groupConv) => {
            const isActive = activeConversationId === groupConv.conversation_id;
            const memberCount = getConversationCharacterIds(groupConv).length;
            return (
              <button
                key={groupConv.conversation_id}
                type="button"
                className={`chat-contact ${isActive ? 'active' : ''}`}
                data-chat-group={groupConv.conversation_id}
                data-testid={`chat-group-${groupConv.conversation_id}`}
                onClick={() => onSelectConversation(groupConv.conversation_id)}
              >
                {groupConv.title} {memberCount}人
              </button>
            );
          })}
        </div>

        <div
          ref={messagesContainerRef}
          className="chat-messages"
          id="chat-messages"
          data-testid="chat-messages-list"
        >
          {activeMessages.length === 0 ? (
            <div className="chat-empty-state">
              {messagesLoading
                ? '调取会话记录...'
                : !activeConversation
                  ? isHistoryView
                    ? '当轮无此臣工密谈记录'
                    : '输入圣谕即可开启密谈'
                  : '尚无往来奏对记录'}
            </div>
          ) : (
            activeMessages.map((msg) => {
              const isMonarch = msg.sender_id === 'monarch';
              const senderName = isMonarch
                ? '圣谕'
                : (characterById.get(msg.sender_id as CharacterId)?.name ??
                  msg.sender_id);
              return (
                <div
                  key={msg.seq}
                  className={`chat-line ${isMonarch ? 'self' : 'other'}`}
                  data-testid={`chat-msg-${msg.seq}`}
                >
                  <div className="chat-line-meta">
                    <span>{senderName}</span>
                    <span>第{msg.source_turn}轮</span>
                    {msg.is_late && <em className="chat-late-badge">迟达</em>}
                    {msg.mentions.length > 0 && (
                      <em className="chat-mention-badge">
                        {msg.mentions
                          .map((id) => `@${characterById.get(id)?.name ?? id}`)
                          .join(' ')}
                      </em>
                    )}
                    {msg.wake_targets.length > 0 && (
                      <em className="chat-receipt-badge">
                        已传召{' '}
                        {msg.wake_targets
                          .map((id) => characterById.get(id)?.name ?? id)
                          .join(' ')}
                      </em>
                    )}
                  </div>
                  <p>{msg.content}</p>
                </div>
              );
            })
          )}
        </div>

        {activeConversation?.kind === 'group' && canInteract && (
          <div className="chat-mention-bar" data-testid="chat-mention-bar">
            <span className="mention-label">传召</span>
            {activeCharIds.map((charId) => {
              const char = characterById.get(charId);
              const checked = groupMentions.includes(charId);
              return (
                <button
                  key={charId}
                  type="button"
                  className={`chat-contact mention-chip ${checked ? 'active' : ''}`}
                  data-testid={`mention-chip-${charId}`}
                  onClick={() => onToggleGroupMention(charId)}
                >
                  @{char?.name ?? charId}
                </button>
              );
            })}
          </div>
        )}

        {chatError && (
          <div className="chat-error-strip" role="alert">
            {chatError}
          </div>
        )}

        <div className="chat-composer">
          <input
            ref={inputRef}
            id="chat-input"
            data-testid="chat-input"
            type="text"
            value={draftText}
            disabled={!canSendInCurrentView || chatBusy}
            placeholder={
              !canInteract
                ? isHistoryView
                  ? '历史旧档只读'
                  : '终局已归档'
                : '降旨垂询...'
            }
            onChange={(e) => onChangeDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                onSendMessage();
              }
            }}
          />
          <button
            type="button"
            className="brass-action primary"
            id="send-chat"
            data-testid="send-chat-btn"
            disabled={
              !canSendInCurrentView ||
              chatBusy ||
              draftText.trim() === ''
            }
            onClick={onSendMessage}
          >
            {chatBusy ? '传旨' : '发送'}
          </button>
        </div>
      </aside>

      {membersPopupOpen && activeConversation?.kind === 'group' && (
        <section
          ref={membersDialogRef}
          className="court-dialog"
          id="group-members-window"
          role="dialog"
          aria-modal="true"
          aria-labelledby="group-members-dialog-title"
          tabIndex={-1}
          data-testid="group-members-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="group-members-dialog-title">廷议成员</strong>
            </div>
            <button
              type="button"
              className="win-btn"
              aria-label="关闭"
              onClick={() => setMembersPopupOpen(false)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <div className="member-list">
              {activeCharIds.map((charId) => {
                const char = characterById.get(charId);
                const officeTitle =
                  activeOfficeByCharacter.get(charId)?.title ?? '候任';
                return (
                  <div key={charId} className="member-row">
                    <span
                      className={`portrait small ${getCharacterPortraitClass(charId)}`}
                      aria-hidden="true"
                    />
                    <div className="member-row-copy">
                      <strong>{char?.name ?? charId}</strong>
                      <span>{officeTitle}</span>
                    </div>
                    {onOpenBiography && (
                      <button
                        type="button"
                        className="icon-btn small"
                        data-bio-person={charId}
                        title="履历"
                        aria-label={`${char?.name ?? charId}履历`}
                        onMouseEnter={(e) =>
                          onHoverBiography?.(charId, e.currentTarget)
                        }
                        onMouseLeave={() => onLeaveBiography?.()}
                        onFocus={(e) =>
                          onHoverBiography?.(charId, e.currentTarget)
                        }
                        onBlur={() => onLeaveBiography?.()}
                        onClick={(e) => {
                          e.stopPropagation();
                          onOpenBiography(charId, e.currentTarget);
                        }}
                      >
                        <svg viewBox="0 0 24 24" aria-hidden="true">
                          <circle
                            cx="12"
                            cy="12"
                            r="8.5"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="1.8"
                          />
                          <path
                            d="M12 10.2v5.4M12 7.4h.01"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                          />
                        </svg>
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </section>
      )}

      {groupCreateOpen && (
        <section
          ref={groupCreateDialogRef}
          className="court-dialog"
          id="group-create-window"
          role="dialog"
          aria-modal="true"
          aria-labelledby="group-create-dialog-title"
          tabIndex={-1}
          data-testid="group-create-dialog"
        >
          <div className="win-bar">
            <div className="win-id">
              <strong id="group-create-dialog-title">廷议</strong>
            </div>
            <button
              type="button"
              className="win-btn"
              aria-label="关闭"
              onClick={() => setGroupCreateOpen(false)}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M5 5l14 14M19 5L5 19"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.9"
                  strokeLinecap="round"
                />
              </svg>
            </button>
          </div>
          <div className="dialog-body">
            <label className="dialog-field" htmlFor="group-topic-input">
              <span>议题</span>
              <input
                id="group-topic-input"
                type="text"
                value={groupTitle}
                onChange={(e) => setGroupTitle(e.target.value)}
              />
            </label>
            <div className="member-checks">
              {appointedCharacters.map((char) => {
                const officeTitle =
                  activeOfficeByCharacter.get(char.character_id)?.title ?? '在任';
                const checked = selectedGroupMemberIds.includes(
                  char.character_id
                );
                return (
                  <label key={char.character_id} className="member-check">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() =>
                        handleToggleNewGroupMember(char.character_id)
                      }
                    />
                    <span
                      className={`portrait small ${getCharacterPortraitClass(char.character_id)}`}
                      aria-hidden="true"
                    />
                    <span>
                      <strong>{char.name}</strong>
                      <em>{officeTitle}</em>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>
          <div className="dialog-actions">
            <button
              type="button"
              className="brass-action primary"
              id="create-group-btn"
              disabled={chatBusy || selectedGroupMemberIds.length === 0}
              onClick={() => void handleConfirmCreateGroup()}
            >
              召集群臣
            </button>
          </div>
        </section>
      )}
    </>
  );
};
